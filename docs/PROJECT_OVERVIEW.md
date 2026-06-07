# Project Overview

## Stack

- `ollama` runs the local model server
- `backend/` is a FastAPI gateway for chat, file upload, and web search
- `ui/` is the browser client served by Nginx

## Main Features

- local chat with Gemma and other Ollama models
- document upload for PDF, DOCX, XLSX, XLS, TXT, MD, JSON, and CSV
- OCR fallback for scanned PDF pages that do not contain embedded text
- document-aware prompts for summarization and question answering
- optional auto web search for current information
- persistent chat memory with end-of-chat summaries
- UI model management for pulling and deleting Ollama models
- automatic default-model bootstrap for fresh clones

## Runtime Flow

1. The browser sends chat requests to `/api/chat`.
2. The backend applies model defaults and optional web search context.
3. The backend can inject saved long-term chat memory into the prompt.
4. The backend forwards the request to Ollama.
5. The UI streams the answer back to the user.

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
   For PDFs, it reads every page and runs OCR only on pages where normal text extraction is empty.
3. The extracted text is stored client-side for the next chat prompt.
4. If the user sends an empty prompt with an attached file, the UI automatically asks for a summary.
