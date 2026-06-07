# Chat Memory

## What It Does

- keeps each active chat session in a file automatically
- summarizes a chat automatically after it stays idle long enough
- appends that summary to one running memory file
- injects the running memory file into future chat prompts automatically
- removes summarized chats from the active pending session queue

## Storage

Chat memory is stored in:

- `backend/data/chat_memory/summary_notes.md`
- `backend/data/chat_memory/active_sessions/*.json`
- `backend/data/chat_memory/sessions/*.json`

## Flow

1. You chat normally in the UI.
2. After each completed assistant reply, the backend updates the active session file automatically.
3. When a session stays idle longer than the configured timeout, the backend summarizes it on a later request.
4. The backend saves:
   - archived raw session history as JSON
   - appended long-term notes as Markdown
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
- active unsummarized chats live in `active_sessions/`
- the memory file is trimmed before prompt injection so it does not grow without limit inside the prompt
- the default idle timeout is `900` seconds
