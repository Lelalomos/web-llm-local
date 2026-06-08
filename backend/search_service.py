import requests
import json
import hashlib
import io
import os
import urllib.parse
import xml.etree.ElementTree as ET
import ipaddress
import re
import socket
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from search_policy import normalize_search_query, rank_search_results

MAX_URL_FETCH_BYTES = 1_000_000
DIRECT_URL_PATTERN = re.compile(r"https?://[^\s<>)\"']+", re.IGNORECASE)
DEFAULT_SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
DEFAULT_MEILI_URL = os.getenv("MEILI_URL", "http://meilisearch:7700")


def extract_http_urls(text: str, limit: int = 3) -> list[str]:
    urls = []
    seen = set()
    for match in DIRECT_URL_PATTERN.finditer(text or ""):
        url = match.group(0).rstrip(".,;:!?)]}")
        if url not in seen:
            urls.append(url)
            seen.add(url)
        if len(urls) >= limit:
            break
    return urls


def _is_public_ip(ip_value: str) -> bool:
    try:
        parsed_ip = ipaddress.ip_address(ip_value)
    except ValueError:
        return False

    return not (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_multicast
        or parsed_ip.is_reserved
        or parsed_ip.is_unspecified
    )


def is_safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or hostname in {"localhost", "localhost.localdomain"}:
        return False

    try:
        resolved_addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    return bool(resolved_addresses) and all(_is_public_ip(address[-1][0]) for address in resolved_addresses)


def _extract_clean_text(html_text: str, max_chars: int) -> str:
    soup = BeautifulSoup(html_text, 'html.parser')
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    clean_text = "\n".join(chunk for chunk in chunks if chunk)
    return clean_text[:max_chars].strip()


def scrape_url_content(url: str, max_chars: int = 1500) -> str:
    """Scrapes clean text content from a URL, removing header/footer/scripts."""
    if not is_safe_public_url(url):
        print(f"[Search Service] Refusing unsafe URL: {url}")
        return ""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        }
        with requests.get(url, headers=headers, timeout=(3, 10), stream=True, allow_redirects=True) as r:
            if r.status_code != 200 or not is_safe_public_url(r.url):
                return ""

            content_type = r.headers.get("content-type", "").lower()
            if content_type and not any(allowed in content_type for allowed in ["text/html", "text/plain", "application/xhtml+xml"]):
                return ""

            raw_chunks = []
            total_bytes = 0
            for chunk in r.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                raw_chunks.append(chunk)
                total_bytes += len(chunk)
                if total_bytes >= MAX_URL_FETCH_BYTES:
                    break

            encoding = r.encoding or r.apparent_encoding or "utf-8"
            html_text = b"".join(raw_chunks).decode(encoding, errors="ignore")
            return _extract_clean_text(html_text, max_chars)
    except Exception as e:
        print(f"[Search Service] Scraper failed for {url}: {e}")
    return ""


def build_direct_url_context(query: str, max_chars: int) -> tuple[str, list[str]]:
    urls = extract_http_urls(query)
    if not urls or max_chars <= 0:
        return "", []

    context_blocks = []
    used_urls = []
    remaining_chars = max_chars
    per_page_chars = min(5000, max(1200, max_chars // max(len(urls), 1)))

    for url in urls:
        content = scrape_url_content(url, min(per_page_chars, remaining_chars))
        if not content:
            continue

        block = f"Website: {url}\nExtracted page text:\n{content}"
        if len(block) > remaining_chars:
            block = block[:remaining_chars].rstrip() + "\n[Website context truncated.]"
        context_blocks.append(block)
        used_urls.append(url)
        remaining_chars -= len(block)
        if remaining_chars <= 0:
            break

    return "\n\n".join(context_blocks).strip(), used_urls

def clean_bing_url(url: str) -> str:
    """Decodes Bing redirect URLs to get the clean landing URL."""
    if "bing.com/ck/a?!" in url:
        try:
            from urllib.parse import urlparse, parse_qs
            import base64
            parsed = urlparse(url)
            queries = parse_qs(parsed.query)
            u_param = queries.get('u')
            if u_param:
                u_str = u_param[0]
                if len(u_str) > 2:
                    b64_part = u_str[2:]
                    b64_part += "=" * ((4 - len(b64_part) % 4) % 4)
                    decoded_bytes = base64.urlsafe_b64decode(b64_part)
                    return decoded_bytes.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[Search Service] Failed to clean Bing URL: {e}")
    return url

def clean_ddg_url(url: str) -> str:
    """Decodes DuckDuckGo redirect URLs to get the clean landing URL."""
    if "uddg=" in url:
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            queries = parse_qs(parsed.query)
            uddg = queries.get('uddg')
            if uddg:
                return uddg[0]
        except Exception as e:
            print("[Search Service] Failed to clean DDG URL:", e)
    elif url.startswith("//"):
        return "https:" + url
    return url

def search_ddg_html(query: str) -> list:
    """Performs a search on DuckDuckGo HTML and returns snippets and URLs."""
    print(f"[Search Service] Running DuckDuckGo HTML search for: '{query}'")
    snippets = []
    try:
        encoded_query = requests.utils.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            containers = soup.find_all('div', class_='result')
            for res in containers[:3]:
                title_a = res.find('a', class_='result__a')
                snippet_a = res.find('a', class_='result__snippet')
                if title_a:
                    title = title_a.get_text().strip()
                    raw_url = title_a.get('href', '')
                    url = clean_ddg_url(raw_url)
                    snippet = snippet_a.get_text().strip() if snippet_a else ""
                    snippets.append({
                        "title": title,
                        "href": url,
                        "body": snippet
                    })
    except Exception as e:
        print(f"[Search Service] DuckDuckGo HTML search failed: {e}")
    return snippets

def decode_google_news_url(url: str) -> str:
    """Decodes Google News redirects to find the direct target news URL."""
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            c_wiz = soup.select_one('c-wiz[data-p]')
            if c_wiz:
                data = c_wiz.get('data-p')
                obj = json.loads(data.replace('%.@.', '["garturlreq",'))
                
                # Replicate the batchexecute POST request
                payload = {'f.req': json.dumps([[['Fbv4je', json.dumps(obj[:-6] + obj[-2:]), 'null', 'generic']]])}
                headers = {'content-type': 'application/x-www-form-urlencoded;charset=UTF-8'}
                
                response = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", 
                                         headers=headers, data=payload, timeout=5)
                
                if response.status_code == 200:
                    clean_text = response.text.replace(")]}'", "").strip()
                    data_json = json.loads(clean_text)
                    inner_data = json.loads(data_json[0][2])
                    return inner_data[1]
    except Exception as e:
        print(f"[Search Service] Failed to decode Google News URL {url}: {e}")
    return url

def search_google_news_rss(query: str) -> list:
    """Performs a Google News RSS search and returns snippets and URLs."""
    print(f"[Search Service] Running Google News RSS search for: '{query}'")
    snippets = []
    try:
        encoded_query = requests.utils.quote(query)
        # Check if Thai/Thailand is mentioned to localize the RSS search
        if any(k in query.lower() for k in ["thailand", "thai", "หุ้น", "ไทย", "bangkok"]):
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=th&gl=TH&ceid=TH:th"
        else:
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            items = root.findall(".//item")
            for item in items[:3]:
                title = item.find("title").text
                google_link = item.find("link").text
                pub_date = item.find("pubDate").text
                real_url = decode_google_news_url(google_link)
                
                # Extract and clean snippet from description tag
                desc_element = item.find("description")
                snippet = desc_element.text if desc_element is not None else ""
                if snippet:
                    snippet = BeautifulSoup(snippet, 'html.parser').get_text().strip()
                
                snippets.append({
                    "title": f"{title} ({pub_date})",
                    "href": real_url,
                    "body": snippet
                })
    except Exception as e:
        print(f"[Search Service] Google News RSS search failed: {e}")
    return snippets

def search_bing_fallback(query: str) -> list:
    """Performs a web search using Bing scraping as a final fallback."""
    print(f"[Search Service] Running fallback Bing search for: '{query}'")
    snippets = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        r = requests.get(f"https://www.bing.com/search?q={requests.utils.quote(query)}", headers=headers, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            results = soup.find_all('li', class_='b_algo')
            for res in results[:3]:
                title_tag = res.find('h2')
                if title_tag:
                    a_tag = title_tag.find('a')
                    if a_tag and a_tag.get('href'):
                        raw_url = a_tag['href']
                        url = clean_bing_url(raw_url)
                        title = a_tag.get_text().strip()
                        
                        # Snippet detection
                        snippet = ""
                        caption_div = res.find('div', class_='b_caption')
                        if caption_div:
                            p_tag = caption_div.find('p')
                            if p_tag:
                                snippet = p_tag.get_text()
                        if not snippet:
                            snippet_div = res.find('div', class_='b_snippet')
                            if snippet_div:
                                snippet = snippet_div.get_text()
                        if not snippet:
                            text_content = res.get_text(separator=" ")
                            snippet = text_content.replace(title, "").strip()
                            if len(snippet) > 200:
                                snippet = snippet[:200] + "..."
                                
                        snippets.append({
                            "title": title,
                            "href": url,
                            "body": snippet.strip()
                        })
    except Exception as e:
        print(f"[Search Service] Fallback Bing search failed: {e}")
    return snippets

def _normalize_search_result(result: dict, source: str = "") -> dict:
    title = str(result.get("title") or result.get("name") or "").strip()
    href = clean_ddg_url(str(result.get("url") or result.get("href") or "").strip())
    body = str(result.get("content") or result.get("body") or result.get("snippet") or "").strip()
    normalized = {"title": title, "href": href, "body": body}
    if source:
        normalized["provider"] = source
    return normalized


def search_searxng(query: str, searxng_url: str = DEFAULT_SEARXNG_URL, timeout: int = 8, limit: int = 6) -> list[dict]:
    print(f"[Search Service] Running SearXNG search for: '{query}'")
    try:
        response = requests.get(
            f"{searxng_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
    except Exception as e:
        print(f"[Search Service] SearXNG search failed: {e}")
        return []

    results = []
    for item in payload.get("results", [])[:limit]:
        result = _normalize_search_result(item, "searxng")
        if result["title"] and result["href"]:
            results.append(result)
    return results


def _meili_headers() -> dict:
    api_key = os.getenv("MEILI_MASTER_KEY", "").strip()
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def search_meilisearch(query: str, app_config: dict | None = None, limit: int = 4) -> list[dict]:
    config = app_config or {}
    if not config.get("meilisearch_enabled", True):
        return []

    meili_url = str(config.get("meilisearch_url") or DEFAULT_MEILI_URL).rstrip("/")
    index_name = str(config.get("meilisearch_index") or "web_search_results").strip()
    timeout = int(config.get("meilisearch_timeout_seconds", 3) or 3)
    try:
        response = requests.post(
            f"{meili_url}/indexes/{index_name}/search",
            headers=_meili_headers(),
            json={"q": query, "limit": limit},
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
    except Exception as e:
        print(f"[Search Service] Meilisearch lookup failed: {e}")
        return []

    results = []
    for item in payload.get("hits", [])[:limit]:
        result = _normalize_search_result(item, "meilisearch")
        if result["title"] and result["href"]:
            results.append(result)
    return results


def index_meilisearch_results(query: str, results: list[dict], app_config: dict | None = None) -> bool:
    config = app_config or {}
    if not config.get("meilisearch_enabled", True) or not results:
        return False

    meili_url = str(config.get("meilisearch_url") or DEFAULT_MEILI_URL).rstrip("/")
    index_name = str(config.get("meilisearch_index") or "web_search_results").strip()
    timeout = int(config.get("meilisearch_timeout_seconds", 3) or 3)
    documents = []
    for result in results:
        href = str(result.get("href", "")).strip()
        if not href:
            continue
        document_id = hashlib.sha256(href.encode("utf-8")).hexdigest()
        documents.append(
            {
                "id": document_id,
                "query": query,
                "title": str(result.get("title", "")),
                "href": href,
                "body": str(result.get("body", "")),
                "provider": str(result.get("provider", "")),
            }
        )

    if not documents:
        return False

    try:
        response = requests.post(
            f"{meili_url}/indexes/{index_name}/documents",
            params={"primaryKey": "id"},
            headers=_meili_headers(),
            json=documents,
            timeout=timeout,
        )
        return response.status_code in {200, 201, 202}
    except Exception as e:
        print(f"[Search Service] Meilisearch index failed: {e}")
        return False


def _legacy_web_search(search_query: str, is_news_query: bool) -> list[dict]:
    """
    Executes Google News / DDG / Bing fallback flow.
    """
    search_results = []
    if is_news_query:
        try:
            search_results = search_google_news_rss(search_query)
        except Exception as e:
            print(f"[Search Service] Google News search failed: {e}")
            
    # Try DuckDuckGo HTML next
    if not search_results:
        try:
            search_results = search_ddg_html(search_query)
        except Exception as e:
            print(f"[Search Service] DuckDuckGo search failed: {e}")
            
    # Try Bing as final fallback
    if not search_results:
        try:
            search_results = search_bing_fallback(search_query)
        except Exception as e:
            print(f"[Search Service] Bing fallback search failed: {e}")
    return search_results


def execute_web_search(query: str, app_config: dict | None = None) -> tuple:
    """
    Executes SearXNG, legacy search, and optional Meilisearch cache, then
    merges, ranks, scrapes top pages, and returns formatted context.
    """
    app_config = app_config or {}
    search_query = normalize_search_query(query)

    print(f"[Search Service] Cleaned search query: '{search_query}'")
    
    is_news_query = any(k in search_query.lower() for k in [
        "news", "stock", "market", "finance", "price", "share", "today", "latest", "recent", "report", "thailand", "thai",
        "ข่าว", "หุ้น", "ตลาด", "การเงิน", "ราคา", "บริษัท"
    ])

    search_provider = str(app_config.get("search_provider", "auto") or "auto")
    search_results = []
    cached_results = search_meilisearch(search_query, app_config)

    if search_provider in {"auto", "searxng"} and app_config.get("searxng_enabled", True):
        search_results.extend(search_searxng(
            search_query,
            str(app_config.get("searxng_url") or DEFAULT_SEARXNG_URL),
            int(app_config.get("searxng_timeout_seconds", 8) or 8),
        ))

    if search_provider in {"auto", "legacy"}:
        search_results.extend(_legacy_web_search(search_query, is_news_query))

    if cached_results:
        search_results.extend(cached_results)

    if not search_results:
        return "No web search results found.", []

    search_results = rank_search_results(search_results, search_query)[:4]
    index_meilisearch_results(search_query, search_results, app_config)

    snippets = []
    top_urls = []
    for r in search_results:
        snippets.append(f"Source: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}")
        if r.get('href') and r.get('href') not in top_urls:
            top_urls.append(r.get('href'))
            
    scraped_blocks = []
    for url in top_urls[:2]:
        print(f"[Search Service] Scraping detailed page: {url}")
        content = scrape_url_content(url)
        if content:
            scraped_blocks.append(f"--- DETAILED PAGE CONTENT FROM {url} ---\n{content}\n--- END DETAILED CONTENT ---")
        
    search_context = "\n\n".join(snippets)
    if scraped_blocks:
        search_context += "\n\n" + "\n\n".join(scraped_blocks)

    return search_context, search_results
