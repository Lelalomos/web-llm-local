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

Use:

- `Write Code` for new code generation
- `Review Code` for findings and risks
- `Edit Code` for minimal code changes
- `Fix Bug` for debugging and corrected code

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
