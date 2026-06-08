TASK_MODE_SYSTEM_PROMPTS = {
    "code_writer": (
        "You are a coding assistant. Write complete runnable code. "
        "Prefer clear structure, small comments only when useful, and include usage notes if needed. "
        "When generating code for API clients, use the correct HTTP method and include the request payload shape. "
        "For this project's /api/chat endpoint, use POST with JSON fields like model, messages, stream, web_search_mode, and optional task_mode. "
        "Return code directly, using markdown code fences when that improves readability."
    ),
    "code_reviewer": (
        "You are a senior code reviewer. Focus on bugs, correctness, regressions, missing tests, and security risks. "
        "List findings first. Keep comments concrete and actionable."
    ),
    "code_editor": (
        "You are a coding assistant editing existing code. Make minimal safe changes, preserve behavior outside the request, "
        "and return the updated code clearly."
    ),
    "bug_fixer": (
        "You are a debugging assistant. Identify the likely root cause, explain the fix briefly, and return the corrected code. "
        "Prefer minimal changes that make the tests pass."
    ),
}


def _ensure_min_num_predict(options: dict, minimum: int) -> None:
    current_value = options.get("num_predict")
    if not isinstance(current_value, int) or current_value < minimum:
        options["num_predict"] = minimum


def apply_task_mode(payload: dict) -> str:
    task_mode = str(payload.pop("task_mode", "general") or "general")
    if task_mode == "general":
        return task_mode

    system_prompt = TASK_MODE_SYSTEM_PROMPTS.get(task_mode)
    if not system_prompt:
        return "general"

    messages = payload.setdefault("messages", [])
    for message in messages:
        if message.get("role") == "system":
            message["content"] = f"{system_prompt}\n\n{message.get('content', '')}".strip()
            break
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})

    if "think" not in payload:
        payload["think"] = False

    options = payload.setdefault("options", {})
    if task_mode == "code_writer":
        _ensure_min_num_predict(options, 1600)
    elif task_mode in {"code_editor", "bug_fixer"}:
        _ensure_min_num_predict(options, 1200)
    elif task_mode == "code_reviewer":
        _ensure_min_num_predict(options, 900)

    return task_mode
