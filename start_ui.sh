#!/bin/bash
# Wrapper to start the local LLM Web UI server
set -e

PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"
UI_DIR="$PROJECT_DIR/ui"
LOGS_DIR="$PROJECT_DIR/logs"
PORT=8000

# Function to check if a port is in use
is_port_in_use() {
    lsof -i :$1 >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$1 "
}

# Find a free port starting from 8000 (excluding backend port 8001)
while is_port_in_use $PORT || [ $PORT -eq 8001 ]; do
    echo "Port $PORT is already in use or reserved. Trying next port..."
    PORT=$((PORT + 1))
done

# Check and start local backend gateway on port 8001
BACKEND_PORT=8001
echo "Checking for existing backend gateway..."
BACKEND_PID=$(pgrep -u $(whoami) -f "uvicorn app:app.*$BACKEND_PORT" || true)
if [ ! -z "$BACKEND_PID" ]; then
    echo "Stopping existing local backend gateway (PID: $BACKEND_PID)..."
    kill "$BACKEND_PID" || true
    sleep 1
fi

echo "Starting local backend gateway on port $BACKEND_PORT..."
# Check if all required python dependencies are met on the host
REQUIRED_MODULES="fastapi uvicorn requests pypdf docx duckduckgo_search multipart openpyxl bs4 xlrd pytesseract pymupdf PIL"
MISSING_DEPENDENCY=0
for mod in $REQUIRED_MODULES; do
    if ! python3 -c "import $mod" >/dev/null 2>&1; then
        echo "Missing required python module: $mod"
        MISSING_DEPENDENCY=1
    fi
done

if [ $MISSING_DEPENDENCY -eq 1 ]; then
    echo "Attempting to install missing host requirements..."
    pip3 install -r "$PROJECT_DIR/backend/requirements.txt" || {
        echo "Error: Failed to install backend dependencies on host. Please run: pip3 install -r backend/requirements.txt"
        exit 1
    }
fi

mkdir -p "$LOGS_DIR"
LD_PRELOAD_VAL=""
if [ -f "/usr/lib/x86_64-linux-gnu/libstdc++.so.6" ]; then
    LD_PRELOAD_VAL="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
fi

nohup setsid env $LD_PRELOAD_VAL PYTHONUNBUFFERED=1 OLLAMA_URL=http://127.0.0.1:11434 python3 -m uvicorn app:app --host 127.0.0.1 --port $BACKEND_PORT --app-dir "$PROJECT_DIR/backend" > "$LOGS_DIR/backend_server.log" 2>&1 < /dev/null &
sleep 2.0

if ! is_port_in_use $BACKEND_PORT; then
    echo "Error: Failed to start backend gateway. Check $LOGS_DIR/backend_server.log for details."
    exit 1
fi

echo "Starting local LLM Web UI server on port $PORT..."

# Stop any previously running python static server from this UI directory
PID=$(pgrep -u $(whoami) -f "python3 -m http.server.*$UI_DIR" || true)
if [ ! -z "$PID" ]; then
    echo "Stopping existing Web UI server (PID: $PID)..."
    kill "$PID" || true
    sleep 1
fi

# Run the python server in the background
nohup setsid python3 -m http.server $PORT --directory "$UI_DIR" > "$LOGS_DIR/ui_server.log" 2>&1 < /dev/null &
sleep 1.0

# Check if the server started successfully
if is_port_in_use $PORT; then
    # Get PIDs for reporting/stopping
    UI_PID=$(pgrep -u $(whoami) -f "python3 -m http.server $PORT" || true)
    BG_PID=$(pgrep -u $(whoami) -f "python3 -m uvicorn app:app.*$BACKEND_PORT" || true)
    echo "============================================="
    echo "🎉 Local LLM Studio successfully started!"
    echo "👉 Open: http://127.0.0.1:$PORT in your browser"
    echo "============================================="
    echo "UI Server logs: $LOGS_DIR/ui_server.log"
    echo "Backend logs:   $LOGS_DIR/backend_server.log"
    [ ! -z "$UI_PID" ] && echo "To stop UI, run:      kill $UI_PID"
    [ ! -z "$BG_PID" ] && echo "To stop Backend, run: kill $BG_PID"
else
    echo "Error: Failed to start Web UI server. Check $LOGS_DIR/ui_server.log for details."
    exit 1
fi
