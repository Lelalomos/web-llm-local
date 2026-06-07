import re
from datetime import datetime, timezone
from urllib.parse import urlparse


AUTO_SEARCH_KEYWORDS = {
    "latest", "recent", "today", "yesterday", "tomorrow", "current", "currently",
    "news", "price", "pricing", "stock", "stocks", "market", "markets", "finance",
    "weather", "forecast", "release", "released", "update", "updated", "version",
    "announcement", "earnings", "share", "shares", "rate", "rates", "exchange",
    "president", "ceo", "live", "schedule", "score", "traffic",
    "ข่าว", "ล่าสุด", "วันนี้", "พรุ่งนี้", "เมื่อวาน", "ราคา", "หุ้น", "ตลาด",
    "การเงิน", "อากาศ", "อัปเดต", "ข่าวสาร", "ค่าเงิน",
}

AUTO_SEARCH_PATTERNS = (
    re.compile(r"\b20\d{2}\b"),
    re.compile(r"\b[A-Z]{2,5}\b"),
    re.compile(r"\bhttps?://", re.IGNORECASE),
)

NO_SEARCH_PHRASES = (
    "write code",
    "python script",
    "debug this",
    "fix this",
    "refactor this",
    "summarize this file",
    "rewrite this",
    "translate this",
    "explain this code",
    "use the file content above",
)

TRUSTED_DOMAINS = {
    "reuters.com": 4,
    "apnews.com": 4,
    "bloomberg.com": 4,
    "wsj.com": 3,
    "ft.com": 3,
    "cnbc.com": 3,
    "marketwatch.com": 3,
    "investing.com": 2,
    "set.or.th": 4,
    "sec.gov": 4,
    "weather.com": 3,
    "noaa.gov": 4,
    "google.com": 1,
    "duckduckgo.com": 1,
    "bing.com": 1,
}

RECENT_DATE_PATTERNS = (
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(20\d{2})/(\d{2})/(\d{2})\b"),
    re.compile(r"\b(20\d{2})\.(\d{2})\.(\d{2})\b"),
)

MONTH_NAME_PATTERN = re.compile(
    r"\b("
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
    r")\s+(\d{1,2}),?\s+(20\d{2})\b",
    re.IGNORECASE,
)

RECENCY_HINTS = ("today", "latest", "recent", "yesterday", "currently", "ล่าสุด", "วันนี้", "เมื่อวาน")


def normalize_search_query(query: str) -> str:
    search_query = (query or "").strip()
    if not search_query:
        return ""

    if "Use the file content above to answer this prompt:" in search_query:
        search_query = search_query.split("Use the file content above to answer this prompt:")[-1].strip()

    search_query = re.sub(r'Context from uploaded file ".*?":.*?--- END OF FILE CONTENT ---', "", search_query, flags=re.DOTALL)
    search_query = re.sub(r"\s+", " ", search_query).strip()

    noise_phrases = [
        "tell me in one sentence", "tell me in a sentence",
        "in one sentence", "in a sentence",
        "explain in detail", "explain in one sentence",
        "write a python script", "write code", "help me",
        "please", "can you", "could you",
    ]

    lowered = search_query.lower()
    for phrase in noise_phrases:
        lowered = lowered.replace(phrase, " ")

    cleaned = re.sub(r"\s+", " ", lowered).strip(" .;:")
    if cleaned:
        search_query = cleaned

    if any(k in search_query for k in [
        "stocks in thailand", "thai stock", "stock in thailand", "thailand stock",
        "thai stocks", "stocks in thai", "thai market", "thailand market",
        "ข่าวหุ้นไทย", "หุ้นไทย", "ดัชนีตลาดหุ้นไทย", "ตลาดหุ้นไทย"
    ]):
        return "SET index Thailand stock news"

    return search_query


def should_auto_search(query: str) -> bool:
    normalized = normalize_search_query(query)
    if not normalized:
        return False

    lowered = normalized.lower()
    if any(phrase in lowered for phrase in NO_SEARCH_PHRASES):
        return False

    if any(keyword in lowered for keyword in AUTO_SEARCH_KEYWORDS):
        return True

    if any(pattern.search(query or "") for pattern in AUTO_SEARCH_PATTERNS):
        return True

    if normalized.endswith("?") and len(normalized.split()) <= 8:
        return True

    return False


def _parse_recent_datetime(text: str) -> datetime | None:
    if not text:
        return None

    for pattern in RECENT_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return datetime(year, month, day, tzinfo=timezone.utc)
            except ValueError:
                return None

    month_match = MONTH_NAME_PATTERN.search(text)
    if month_match:
        month_text, day_text, year_text = month_match.groups()
        try:
            parsed = datetime.strptime(f"{month_text} {day_text} {year_text}", "%B %d %Y")
        except ValueError:
            try:
                parsed = datetime.strptime(f"{month_text} {day_text} {year_text}", "%b %d %Y")
            except ValueError:
                return None
        return parsed.replace(tzinfo=timezone.utc)

    return None


def _recency_score(result: dict) -> int:
    combined_text = " ".join(str(result.get(key, "")) for key in ("title", "body"))
    parsed_date = _parse_recent_datetime(combined_text)
    if parsed_date is None:
        lowered = combined_text.lower()
        return 2 if any(hint in lowered for hint in RECENCY_HINTS) else 0

    now = datetime.now(timezone.utc)
    age_days = max((now - parsed_date).days, 0)
    if age_days <= 1:
        return 6
    if age_days <= 7:
        return 4
    if age_days <= 30:
        return 2
    if age_days <= 180:
        return 1
    return 0


def canonical_result_key(result: dict) -> str:
    href = str(result.get("href", "")).strip().lower()
    if href:
        parsed = urlparse(href)
        host = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{host}{path}"

    title = re.sub(r"\s+", " ", str(result.get("title", "")).strip().lower())
    return title


def dedupe_search_results(results: list[dict]) -> list[dict]:
    deduped_results = []
    seen_keys = set()
    seen_host_title_pairs = set()

    for result in results:
        canonical_key = canonical_result_key(result)
        if canonical_key and canonical_key in seen_keys:
            continue

        href = str(result.get("href", "")).strip().lower()
        parsed = urlparse(href) if href else None
        host = parsed.netloc.replace("www.", "") if parsed else ""
        normalized_title = re.sub(r"\s+", " ", str(result.get("title", "")).strip().lower())
        host_title_pair = (host, normalized_title)
        if host and normalized_title and host_title_pair in seen_host_title_pairs:
            continue

        if canonical_key:
            seen_keys.add(canonical_key)
        if host and normalized_title:
            seen_host_title_pairs.add(host_title_pair)
        deduped_results.append(result)

    return deduped_results


def score_search_result(result: dict, query: str) -> int:
    title = str(result.get("title", "")).lower()
    body = str(result.get("body", "")).lower()
    href = str(result.get("href", "")).lower()
    query_terms = [term for term in re.findall(r"[a-z0-9\u0E00-\u0E7F]+", query.lower()) if len(term) > 2]

    score = 0
    for term in query_terms:
        if term in title:
            score += 3
        if term in body:
            score += 1

    parsed = urlparse(href)
    netloc = parsed.netloc.replace("www.", "")
    for trusted_domain, weight in TRUSTED_DOMAINS.items():
        if netloc.endswith(trusted_domain):
            score += weight
            break

    if any(word in title for word in ("today", "latest", "recent", "2026", "2025", "ล่าสุด", "วันนี้")):
        score += 2

    score += _recency_score(result)

    return score


def rank_search_results(results: list[dict], query: str) -> list[dict]:
    deduped_results = dedupe_search_results(results)
    return sorted(deduped_results, key=lambda item: score_search_result(item, query), reverse=True)
