import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config_store import load_app_config
from search_enhancer import enhance_search_context
from search_policy import normalize_search_query
from search_service import execute_web_search


def main() -> int:
    parser = argparse.ArgumentParser(description="Run project web search and print raw/enhanced context.")
    parser.add_argument("query", help="Search query to run")
    parser.add_argument("--enhance", action="store_true", help="Use the configured small model to enhance context")
    parser.add_argument("--provider", choices=["auto", "searxng", "legacy"], help="Override search provider for this run")
    parser.add_argument("--max-context", type=int, default=2500, help="Characters of context to print")
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://ollama:11434"))
    args = parser.parse_args()

    normalized_query = normalize_search_query(args.query)
    print(f"Original query: {args.query}")
    print(f"Normalized query: {normalized_query}")
    print("Search libraries: requests + BeautifulSoup; providers: SearXNG, Google News RSS, DuckDuckGo HTML, Bing fallback; cache: Meilisearch")
    print()

    app_config = load_app_config()
    if args.provider:
        app_config["search_provider"] = args.provider

    raw_context, results = execute_web_search(args.query, app_config)
    print(f"Result count: {len(results)}")
    for index, result in enumerate(results, 1):
        print(f"{index}. {result.get('title', '')}")
        print(f"   URL: {result.get('href', '')}")
        print(f"   Snippet: {result.get('body', '')[:240]}")

    print("\n--- Raw Search Context ---")
    print(raw_context[: args.max_context])
    if len(raw_context) > args.max_context:
        print("\n[raw context truncated]")

    if args.enhance:
        enhanced_context, enhanced, model = enhance_search_context(args.ollama_url, args.query, raw_context, results, app_config)
        print("\n--- Enhanced Search Context ---")
        print(f"Enhanced: {enhanced}")
        print(f"Enhancer model: {model or 'none'}")
        print(enhanced_context[: args.max_context])
        if len(enhanced_context) > args.max_context:
            print("\n[enhanced context truncated]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
