#!/bin/bash
# Script to safely stop and bring down the Docker Compose environment
set -e

PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"

echo "=== Bringing Down Gemma 4 Local Docker Environment ==="
docker compose down --remove-orphans

echo ""
echo "=========================================================="
echo "👋 Local LLM Studio containers have been stopped and removed."
echo "   Note: Your downloaded models in the volume mount are preserved."
echo "=========================================================="
echo ""
