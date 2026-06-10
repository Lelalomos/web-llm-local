# Chat Memory

## What It Does

- keeps each active chat session in a file automatically
- summarizes a chat automatically after it stays idle long enough
- appends only the summary text to one running memory file
- injects the running memory file into future chat prompts automatically
- removes summarized chats from the active pending session queue

## Storage

Chat memory is stored in:

- `data/chat_memory/summary_notes.md`
- `data/chat_memory/active_sessions/*.json`
- `data/chat_memory/sessions/*.json`

## Flow

1. You chat normally in the UI.
2. After each completed assistant reply, the backend updates the active session file automatically.
3. When a session stays idle longer than the configured timeout, the backend summarizes it on a later request.
4. The backend saves:
   - archived raw session history as JSON
   - appended long-term summary text as Markdown
5. The summarized session is removed from `active_sessions/`.
6. Future `/api/chat` requests automatically include the saved long-term notes as memory context.

## Summary Format

The model is asked to write these sections:

- `## Session Goal`
- `## Important Facts`
- `## User Preferences`
- `## Personal Style`
- `## Open Questions`
- `## Useful Follow-ups`

## Notes

- all models use the same saved memory file
- raw history is kept separately from the running summary file
- the running memory file does not include session id, model name, task mode, or timestamp metadata
- active unsummarized chats live in `active_sessions/`
- the memory file is trimmed before prompt injection so it does not grow without limit inside the prompt
- the default injected memory window is `12000` characters and can be changed with `CHAT_MEMORY_PROMPT_CHARS`
- prompt memory injection is controlled per task mode by `memory_used` in `backend/config/app_config.json`
- uploaded-file requests use the `memory_used.upload_file` setting and default to not injecting saved summary memory
- web-search requests do not inject saved summary memory even when their task mode is enabled in `memory_used`
- summary generation can read relevant old memory notes before summarizing the recent chat
- summary memory retrieval is controlled by `CHAT_MEMORY_SUMMARY_RAG_ENABLED` and `CHAT_MEMORY_SUMMARY_RAG_CHARS`
- the prompt used to ask the model for memory summaries is configured with `chat_summary_prompt` in the app config popup
- saved chat memory and raw history can be removed with the app config popup or `DELETE /api/chat/memory`
- the default idle timeout is `900` seconds

## Task Mode Memory Config

Configure which task modes can read saved summary memory:

```json
{
  "memory_used": {
    "general": true,
    "code_writer": true,
    "code_reviewer": true,
    "code_editor": false,
    "bug_fixer": false,
    "upload_file": false
  }
}
```

Supported task mode keys are `general`, `code_writer`, `code_reviewer`, `code_editor`, and `bug_fixer`.
Uploaded-file requests use the special `upload_file` key.
Each task mode is controlled separately.
