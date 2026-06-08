# Project Overview

## Stack

- `ollama` runs the local model server
- `backend/` is a FastAPI gateway for chat, file upload, and web search
- `ui/` is the browser client served by Nginx

## Main Features

- local chat with Gemma and other Ollama models
- document upload for PDF, DOCX, XLSX, XLS, TXT, MD, JSON, CSV, JPG, JPEG, and PNG
- configurable OCR for scanned PDF pages and image uploads using Qwen-VL, Surya/Docling, or Tesseract fallback
- document-aware prompts for summarization and question answering
- optional auto web search for current information
- local SearXNG metasearch as primary web-search provider
- optional Meilisearch cache for previously found web results
- small-model intent routing for task mode and auto web-search decisions
- small-model search context enhancement before final answer generation
- direct website context when a user pastes an `http` or `https` URL
- persistent chat memory with end-of-chat summaries
- UI model management for pulling and deleting Ollama models
- file-backed config that the backend reads on each chat request
- optional skill markdown injection from `backend/skill/*.md`
- automatic default-model bootstrap for fresh clones

## Runtime Flow

1. The browser sends chat requests to `/api/chat`.
2. The UI asks `/api/task-mode/infer` to classify the latest prompt with the configured small interpreter model.
3. The backend applies model defaults and optional web search context.
4. In auto search mode, the backend can use the same interpreter model to decide whether web search is needed and to produce a cleaner search query.
5. For web search in `auto` provider mode, the backend combines SearXNG, legacy search providers, and cached Meilisearch results.
6. Legacy search providers are Google News RSS, DuckDuckGo HTML, and Bing fallback.
7. Forced `searxng` or `legacy` provider modes are available for debugging one live provider path.
8. The backend indexes successful web results into Meilisearch for later reuse.
9. The backend can ask a small model to turn raw search snippets/page text into a grounded research brief.
10. If the latest prompt contains a public website URL, the backend fetches clean page text and injects it as website context.
11. The backend reads the saved app config and optional skill markdown before prompt assembly.
12. The backend can inject saved long-term chat memory into the prompt.
13. The backend forwards the request to Ollama.
14. The UI streams the answer back to the user.

## Chat Memory Flow

1. The user chats normally.
2. After each completed assistant reply, the backend updates the active session file automatically.
3. When an older session stays idle long enough, the backend summarizes it with the saved model and task mode.
4. The raw session is archived as JSON.
5. The running memory summary file is appended in Markdown.
6. The summarized session is removed from the active pending queue.
7. Future chats automatically receive that memory file as prompt context.

## Document Upload Flow

1. The UI uploads a file to `/api/upload`.
2. The backend extracts text from the uploaded file.
   For PDFs, it reads embedded text first and runs configured OCR only when needed.
3. The extracted text is stored client-side for the next chat prompt.
4. If the user sends an empty prompt with an attached file, the UI automatically asks for a summary.
