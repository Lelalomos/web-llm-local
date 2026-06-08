# Agentic Coding

## Supported Task Modes

- `general`
- `code_writer`
- `code_reviewer`
- `code_editor`
- `bug_fixer`

## Backend API

Send `task_mode` with `/api/chat`.

Example:

```json
{
  "model": "gemma4:e2b",
  "messages": [
    {"role": "user", "content": "Write a Python function that adds two numbers."}
  ],
  "stream": false,
  "web_search_mode": "off",
  "task_mode": "code_writer"
}
```

## UI

The sidebar now includes a `Task Mode` selector.
Before each chat request, the UI calls `/api/task-mode/infer`.
The backend uses the configured small interpreter model to classify the latest prompt.
If the interpreter is unavailable, slow, or returns invalid output, the UI falls back to local keyword rules.

Use:

- `Write Code` for new code generation
- `Review Code` for findings and risks
- `Edit Code` for minimal code changes
- `Fix Bug` for debugging and corrected code

## Web Search Notes

- Auto web search is skipped for code-writing/editing/fixing modes unless search is explicitly enabled.
- This prevents coding prompts like `write rust for search engine` from receiving unrelated web search snippets.
- In auto mode, the backend can use the small interpreter model to decide if search is needed and to produce a cleaner search query.
- When web search returns results, the backend can use a small model to create a grounded research brief from the raw snippets and scraped page text.
- If a user includes a public `http` or `https` URL, the backend can fetch that exact page as website context.

## Intent Interpreter Config

The interpreter is controlled by `backend/config/app_config.json`:

```json
{
  "task_mode_interpreter_enabled": true,
  "task_mode_interpreter_model": "gemma2:2b",
  "task_mode_interpreter_timeout_seconds": 30
}
```

Use a small installed Ollama model here. The default is `gemma2:2b` because it is small and already bootstrapped by this project. If the model is missing or times out, the app falls back safely.

## Search Enhancement Config

Search enhancement is controlled by `backend/config/app_config.json`:

```json
{
  "search_context_enhancer_enabled": true,
  "search_context_enhancer_model": "qwen2.5:0.5b",
  "search_context_enhancer_timeout_seconds": 45,
  "search_context_enhancer_max_chars": 6000
}
```

The enhancer tries the configured model first, then falls back to the task-mode interpreter model, then `gemma2:2b`.
The search libraries are `requests` and `BeautifulSoup`.
In `auto` provider mode, the backend combines SearXNG, legacy providers, and cached Meilisearch results before ranking.
Legacy providers are Google News RSS for news-like queries, DuckDuckGo HTML, and Bing scraping fallback.
Meilisearch stores successful search results and mixes cached local results into later searches.

Search provider config:

```json
{
  "search_provider": "auto",
  "searxng_enabled": true,
  "searxng_url": "http://searxng:8080",
  "searxng_timeout_seconds": 8,
  "meilisearch_enabled": true,
  "meilisearch_url": "http://meilisearch:7700",
  "meilisearch_index": "web_search_results",
  "meilisearch_timeout_seconds": 3
}
```

`search_provider` can be `auto`, `searxng`, or `legacy`.
Use `auto` for combined search. Use `searxng` or `legacy` only when debugging one provider path.

Debug search output:

```bash
docker compose run --rm backend python scripts/run_search_debug.py "latest gemma release news" --enhance
```

Force SearXNG in the debug script:

```bash
docker compose run --rm backend python scripts/run_search_debug.py "latest gemma release news" --provider searxng --enhance
```

## Script

Use the helper script to send a coding prompt directly:

```bash
python3 scripts/send_code_prompt.py
```

Example custom prompt:

```bash
python3 scripts/send_code_prompt.py --prompt "Write Python code that calls http://127.0.0.1:8000/api/chat and prints the response."
```

## Working API Client Example

Use the included project-aware client script when you want the correct payload for this gateway:

```bash
python3 scripts/call_local_model.py "Write a short Python function that adds two numbers."
```

Example with coding mode:

```bash
python3 scripts/call_local_model.py --task-mode code_writer "Write Python code that calculates the average of a list."
```
