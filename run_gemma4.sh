#!/bin/bash
# Wrapper script to run and interact with local Gemma 4 environment

PROJECT_DIR="/home/lelalomos/Desktop/gigadrive/research/gemma4-local"
BIN_DIR="$PROJECT_DIR/bin"
MODELS_DIR="$PROJECT_DIR/models"
LOGS_DIR="$PROJECT_DIR/logs"

# Ensure environment variables are set correctly
export OLLAMA_MODELS="$MODELS_DIR"
export OLLAMA_HOST="127.0.0.1:11434"

show_help() {
    echo "Gemma 4 Local CLI Wrapper"
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start       Start Ollama server in background"
    echo "  stop        Stop local Ollama server"
    echo "  status      Check Ollama server status and logs"
    echo "  test        Run Python test script to verify Gemma 4 is working"
    echo "  cli [...]   Run direct Ollama commands (e.g. '$0 cli run gemma4:e2b' or '$0 cli list')"
    echo "  help        Show this help message"
}

case "$1" in
    start)
        # Check if already running
        PID=$(pgrep -f "$BIN_DIR/ollama serve" || true)
        if [ ! -z "$PID" ]; then
            echo "Ollama server is already running with PID $PID."
            exit 0
        fi
        echo "Starting Ollama server in the background..."
        nohup "$BIN_DIR/ollama" serve > "$LOGS_DIR/ollama.log" 2>&1 &
        echo "Ollama server started. Logs are written to $LOGS_DIR/ollama.log"
        ;;
    stop)
        PID=$(pgrep -f "$BIN_DIR/ollama serve" || true)
        if [ -z "$PID" ]; then
            echo "Ollama server is not running."
        else
            echo "Stopping Ollama server (PID: $PID)..."
            kill "$PID"
            echo "Stopped."
        fi
        ;;
    status)
        PID=$(pgrep -f "$BIN_DIR/ollama serve" || true)
        if [ -z "$PID" ]; then
            echo "Ollama server status: NOT RUNNING"
        else
            echo "Ollama server status: RUNNING (PID: $PID)"
            echo "Listening on: http://$OLLAMA_HOST"
        fi
        echo ""
        echo "Recent Logs ($LOGS_DIR/ollama.log):"
        tail -n 10 "$LOGS_DIR/ollama.log" 2>/dev/null || echo "No logs found yet."
        ;;
    test)
        python3 "$PROJECT_DIR/test_gemma4.py"
        ;;
    cli)
        shift
        "$BIN_DIR/ollama" "$@"
        ;;
    *)
        if [ ! -z "$1" ]; then
            # Default to passing arguments to Ollama binary directly
            "$BIN_DIR/ollama" "$@"
        else
            show_help
        fi
        ;;
esac
