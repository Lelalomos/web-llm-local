#!/bin/bash
# Script to stop local standalone processes and launch the Docker-compose production environment
set -e

PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"

echo "=== Switching to Production-grade Docker Deployment ==="

# 1. Stop standalone local Ollama server if running on port 11434
echo "Checking for processes running on port 11434 (Ollama)..."
OLLAMA_PID=$(lsof -t -i:11434 || true)
if [ ! -z "$OLLAMA_PID" ]; then
    echo "Killing process listening on port 11434 (PID: $OLLAMA_PID)..."
    kill -9 $OLLAMA_PID || true
    sleep 2
fi

# 2. Stop standalone python static web server if running on port 8000
echo "Checking for processes running on port 8000 (Web UI)..."
UI_PID=$(lsof -t -i:8000 || true)
if [ ! -z "$UI_PID" ]; then
    echo "Killing process listening on port 8000 (PID: $UI_PID)..."
    kill -9 $UI_PID || true
    sleep 2
fi

# 3. Build and launch Docker Compose
echo "Building and launching containers..."
docker compose down -v --remove-orphans || true
docker compose up --build -d

echo ""
echo "=========================================================="
echo "🎉 Local LLM Studio is now running inside Docker!"
echo "👉 Open: http://127.0.0.1:8000 in your browser"
echo "=========================================================="
echo "Notes:"
echo "  - Both Ollama and the UI are packaged into containers."
echo "  - Nginx handles static file hosting and reverse proxying."
echo "  - Ollama is configured to use Nvidia GPU (GTX 1650)."
echo "  - Volume mounts preserve your previously downloaded models."
echo ""
echo "To view container logs:"
echo "  docker compose logs -f"
echo ""
echo "To stop the containers:"
echo "  docker compose down"
echo "=========================================================="
