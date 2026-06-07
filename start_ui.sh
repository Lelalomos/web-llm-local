#!/bin/bash
# Wrapper to start the local LLM Web UI server
set -e

PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"
UI_DIR="$PROJECT_DIR/ui"
LOGS_DIR="$PROJECT_DIR/logs"
PORT=8000

# Function to check if a port is in use
is_port_in_use() {
    lsof -i :$1 >/dev/null 2>&1 || netstat -tuln | grep -q ":$1 "
}

# Find a free port starting from 8000
while is_port_in_use $PORT; do
    echo "Port $PORT is already in use. Trying next port..."
    PORT=$((PORT + 1))
done

echo "Starting local LLM Web UI server on port $PORT..."
mkdir -p "$LOGS_DIR"

# Stop any previously running python static server from this UI directory
PID=$(pgrep -f "python3 -m http.server.*$UI_DIR" || true)
if [ ! -z "$PID" ]; then
    echo "Stopping existing Web UI server (PID: $PID)..."
    kill "$PID"
    sleep 1
fi

# Run the python server in the background
nohup python3 -m http.server $PORT --directory "$UI_DIR" > "$LOGS_DIR/ui_server.log" 2>&1 &
SERVER_PID=$!

sleep 1

# Check if the server started successfully
if ps -p $SERVER_PID > /dev/null; then
    echo "============================================="
    echo "🎉 Web UI successfully started!"
    echo "👉 Open: http://127.0.0.1:$PORT in your browser"
    echo "============================================="
    echo "Server logs: $LOGS_DIR/ui_server.log"
    echo "To stop the server, run: kill $SERVER_PID"
else
    echo "Error: Failed to start Web UI server. Check $LOGS_DIR/ui_server.log for details."
    exit 1
fi
