# Local Gemma 4 & Ollama Docker Studio

This directory contains a **production-grade, containerized local installation of Ollama, Gemma 4, and a premium chat Web UI** with reverse proxying and GPU acceleration.

## 🏗️ Architecture Layout
*   `bin/`: Contains the host `ollama` executable (for standalone host use).
*   `models/`: Contains the downloaded model weights. **Mounted to the Docker container** to share files.
*   `logs/`: Contains host server logs and container start scripts.
*   `ui/`: Web chat application (HTML/CSS/JS) with Highlight.js code styling and click-to-copy buttons.
*   `nginx.conf`: Custom Nginx configuration enabling relative REST API proxying with **disabled buffering** to support real-time token streaming.
*   `Dockerfile`: Builds the web interface container using `nginx:alpine`.
*   `docker-compose.yml`: Defers configuration for running Ollama (with GPU CUDA support) and Nginx Web UI containers together.
*   `start_docker.sh`: Automated script to clean up standalone processes and spin up the Docker-compose stack.

---

## 🚀 Quick Start (Production Docker)

To run the complete system inside Docker:

1.  **Launch the containers:**
    ```bash
    ./start_docker.sh
    ```
2.  **Open in Browser:**
    👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

This launches:
-   **Web UI**: Running on **port 8000** (proxied by Nginx).
-   **Ollama GPU Service**: Running on **port 11434** inside the Docker network (accessible to the UI and exposed on the host).

---

## 🛠️ CLI Operations (Inside Docker)

You can run commands directly inside the active Ollama container:

### Check Model List and Download Progress
```bash
docker exec local-ollama-service ollama list
```

### Run Gemma 4 Edge (E2B) in Interactive Terminal
Once the background download completes:
```bash
docker exec -it local-ollama-service ollama run gemma4:e2b
```

---

## 🧼 Standalone Host Commands (Fallback)

If you prefer to run Ollama and the UI directly on your host machine without Docker:

*   **Start host Ollama**: `./run_gemma4.sh start`
*   **Start host static UI**: `./start_ui.sh` (access via port 8000)
*   **Run CLI on host**: `./run_gemma4.sh run qwen2.5:0.5b`
*   **Stop host servers**: `./run_gemma4.sh stop`
