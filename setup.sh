#!/bin/bash
# Setup Gemma 4 local environment
set -e

# Define project directories
PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"
BIN_DIR="$PROJECT_DIR/bin"
MODELS_DIR="$PROJECT_DIR/models"
LOGS_DIR="$PROJECT_DIR/logs"

echo "=== Setting up Gemma 4 Local Environment ==="
mkdir -p "$BIN_DIR" "$MODELS_DIR" "$LOGS_DIR"

# Download and extract Ollama if binary doesn't exist
if [ ! -f "$BIN_DIR/ollama" ]; then
    echo "Downloading Ollama Linux AMD64 package (tar.zst)..."
    TEMP_ZST="$PROJECT_DIR/ollama-linux-amd64.tar.zst"
    curl -L "https://ollama.com/download/ollama-linux-amd64.tar.zst" -o "$TEMP_ZST"
    
    echo "Extracting Ollama files (bin and lib)..."
    unzstd -c "$TEMP_ZST" | tar -x -C "$PROJECT_DIR" bin lib
    rm "$TEMP_ZST"
    chmod +x "$BIN_DIR/ollama"
    echo "Ollama installed locally."
else
    echo "Ollama binary already exists at $BIN_DIR/ollama."
fi

# Stop any running ollama instance running from this directory
echo "Checking for running Ollama server..."
PID=$(pgrep -f "$BIN_DIR/ollama serve" || true)
if [ ! -z "$PID" ]; then
    echo "Stopping existing local Ollama process (PID: $PID)..."
    kill "$PID"
    sleep 2
fi

# Set environment variables for Ollama
export OLLAMA_MODELS="$MODELS_DIR"
export OLLAMA_HOST="127.0.0.1:11434"
export LD_LIBRARY_PATH="$PROJECT_DIR/lib/ollama:$LD_LIBRARY_PATH"

echo "Starting Ollama server in background..."
nohup "$BIN_DIR/ollama" serve > "$LOGS_DIR/ollama.log" 2>&1 &
SERVER_PID=$!

echo "Waiting for Ollama server to start (on port 11434)..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:11434/" > /dev/null; then
        echo "Ollama server is up and running!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: Ollama server failed to start. Check $LOGS_DIR/ollama.log for details."
        exit 1
    fi
    sleep 1
done

# Pull Gemma 4 Edge 2B model for testing
echo "Pulling Gemma 4 Edge 2B model (gemma4:e2b)..."
"$BIN_DIR/ollama" pull gemma4:e2b

echo "=== Gemma 4 local setup completed successfully! ==="
echo "Local server PID: $SERVER_PID"
echo "To manage or query the model, use: $BIN_DIR/ollama run gemma4:e2b"
