import requests


DEFAULT_SEARCH_ENHANCER_MODEL = "gemma2:2b"


def _candidate_models(app_config: dict) -> list[str]:
    candidates = [
        str(app_config.get("search_context_enhancer_model") or "").strip(),
        str(app_config.get("task_mode_interpreter_model") or "").strip(),
        DEFAULT_SEARCH_ENHANCER_MODEL,
    ]
    return [model for index, model in enumerate(candidates) if model and candidates.index(model) == index]


def _format_result_index(search_results: list[dict]) -> str:
    lines = []
    for index, result in enumerate(search_results or [], 1):
        title = str(result.get("title", "")).strip()
        href = str(result.get("href", "")).strip()
        body = str(result.get("body", "")).strip()
        lines.append(f"[{index}] {title}\nURL: {href}\nSnippet: {body}")
    return "\n\n".join(lines).strip()


def _build_enhancer_prompt(query: str, raw_context: str, search_results: list[dict], max_chars: int) -> str:
    result_index = _format_result_index(search_results)
    return (
        "You improve web search context for a local LLM chat app.\n"
        "Use only the provided search results and raw page text. Do not invent facts, sources, dates, or URLs.\n"
        "Write a compact research brief with these sections:\n"
        "1. Answer Focus: what the final model should answer.\n"
        "2. Key Facts: bullet facts grounded in the provided text.\n"
        "3. Source Map: map each important fact to a URL.\n"
        "4. Weak Evidence: mention missing or uncertain details.\n\n"
        f"User query:\n{query[:1000]}\n\n"
        f"Search result index:\n{result_index[:3000]}\n\n"
        f"Raw search context:\n{raw_context[:max_chars]}"
    )


def enhance_search_context(
    ollama_url: str,
    query: str,
    raw_context: str,
    search_results: list[dict],
    app_config: dict,
) -> tuple[str, bool, str]:
    if not app_config.get("search_context_enhancer_enabled", True):
        return raw_context, False, ""
    if not raw_context.strip() or raw_context == "No web search results found.":
        return raw_context, False, ""

    timeout = int(app_config.get("search_context_enhancer_timeout_seconds", 45) or 45)
    max_chars = int(app_config.get("search_context_enhancer_max_chars", 6000) or 6000)
    prompt = _build_enhancer_prompt(query, raw_context, search_results, max_chars)

    for model in _candidate_models(app_config):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_predict": 700,
                "num_gpu": 999,
            },
        }

        try:
            response = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=timeout)
            response.raise_for_status()
            enhanced_context = str(response.json().get("message", {}).get("content", "")).strip()
        except (requests.exceptions.RequestException, ValueError, TypeError):
            continue

        if not enhanced_context:
            continue

        combined_context = (
            "Small-model Search Brief:\n"
            f"{enhanced_context}\n\n"
            "Raw Search Evidence:\n"
            f"{raw_context}"
        )
        return combined_context, True, model

    return raw_context, False, ""
