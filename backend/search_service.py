import requests
import json
import io
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from search_policy import normalize_search_query, rank_search_results

def scrape_url_content(url: str) -> str:
    """Scrapes clean text content from a URL, removing header/footer/scripts."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Decompose heavy junk elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                tag.decompose()
            text = soup.get_text(separator=" ")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            return clean_text[:1500].strip()
    except Exception as e:
        print(f"[Search Service] Scraper failed for {url}: {e}")
    return ""

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

def execute_web_search(query: str) -> tuple:
    """
    Executes Google News / DDG / Bing search flow, scrapes top pages,
    and returns a formatted context string along with the raw list of results.
    """
    search_query = normalize_search_query(query)

    print(f"[Search Service] Cleaned search query: '{search_query}'")
    
    # 2. Check if news related
    is_news_query = any(k in search_query.lower() for k in [
        "news", "stock", "market", "finance", "price", "share", "today", "latest", "recent", "report", "thailand", "thai",
        "ข่าว", "หุ้น", "ตลาด", "การเงิน", "ราคา", "บริษัท"
    ])
    
    search_results = []
    
    # Try Google News RSS first for news queries
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

    if not search_results:
        return "No web search results found.", []

    search_results = rank_search_results(search_results, search_query)[:4]

    # 3. Format context & scrape top 2 pages
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
