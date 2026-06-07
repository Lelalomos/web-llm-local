#!/bin/bash
# Script to pull Gemma 4 12B via Hugging Face GGUF and create 'gemma4:12b' alias in Ollama
set -e

PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"

echo "=== Starting Gemma 4 12B Pull and Alias Creation ==="
echo "1. Pulling Hugging Face GGUF model..."
docker exec local-ollama-service ollama pull hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M

echo "2. Creating alias 'gemma4:12b' in Ollama..."
docker exec local-ollama-service sh -c "echo 'FROM hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M' > /tmp/ModelFile && ollama create gemma4:12b -f /tmp/ModelFile && rm /tmp/ModelFile"

echo "=== Gemma 4 12B successfully added to Ollama as 'gemma4:12b'! ==="
