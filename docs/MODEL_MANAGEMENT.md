# Model Management

## What It Does

- lists installed Ollama models in the UI
- lets you pull a model by name
- lets you delete an installed model

## Backend Endpoints

- `GET /api/tags`
- `POST /api/models/pull`
- `POST /api/models/delete`

## UI Flow

1. Open the sidebar.
2. In `Manage Models`, type a model name like `qwen2.5:0.5b`.
3. Click `Pull` to download it.
4. Choose an installed model from the delete list.
5. Click `Delete` to remove it.

## Notes

- pull and delete actions are real Ollama operations
- delete asks for confirmation in the UI
- model names are validated before the backend forwards them to Ollama
