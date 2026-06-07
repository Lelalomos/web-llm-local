# First Run

## Goal

After cloning this repo, a user should be able to:

1. build Docker images
2. start the stack
3. wait for the default Ollama model to download automatically
4. use the app

## Important Notes

- Ollama model files are not stored in Git
- the repo auto-pulls a default model on first run if the models directory is empty
- the default model is controlled by `DEFAULT_OLLAMA_MODEL`
- the current default is `gemma2:2b`

## Quick Start

```bash
docker compose up -d --build
```

Then open:

```text
http://127.0.0.1:8000
```

## First-Run Behavior

- if no model exists in the local Ollama models directory, the backend asks Ollama to pull the default model automatically
- the UI keeps checking until a model appears
- once the model is available, the app becomes usable without manual model setup

## Optional

To change the default model on first run:

```bash
DEFAULT_OLLAMA_MODEL=qwen2.5:0.5b docker compose up -d --build
```
