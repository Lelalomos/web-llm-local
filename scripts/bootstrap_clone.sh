#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

docker compose up -d --build

echo "Stack started."
echo "Open http://127.0.0.1:8000"
echo "If this is the first run, Ollama will pull the default model automatically."
