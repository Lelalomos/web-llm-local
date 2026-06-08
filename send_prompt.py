#!/usr/bin/env python3
import sys
import argparse
import requests
import json

def stream_chat(url, model, prompt, task_mode):
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": True,
        "task_mode": task_mode,
        "web_search_mode": "off"
    }

    print(f"\nSending prompt to gateway: {url}")
    print(f"Model: {model} | Task Mode: {task_mode}")
    print("-" * 50)
    print("Response: ", end="", flush=True)

    try:
        response = requests.post(url, json=payload, stream=True, timeout=120)
        if response.status_code != 200:
            print(f"\nError: Gateway returned status code {response.status_code}")
            print(response.text)
            return

        # Read the NDJSON stream
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    
                    # Handle search status messages if web search is ever on
                    if data.get("type") == "search_status":
                        continue
                        
                    content = data.get("message", {}).get("content", "")
                    if content:
                        print(content, end="", flush=True)
                except Exception:
                    pass
        print("\n" + "-" * 50)
    except requests.exceptions.ConnectionError:
        print(f"\nError: Could not connect to the gateway at {url}.")
        print("Please check if the gateway is running.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Query the local Gemma 4 / Ollama Gateway.")
    parser.add_argument("prompt", nargs="?", help="Prompt text to send to the model.")
    parser.add_argument("--port", type=int, default=8000, help="Gateway port (8000 for Docker Nginx, 8001 for Standalone).")
    parser.add_argument("--model", default="gemma4:e2b", help="Model name (e.g., gemma4:e2b, gemma2:2b).")
    parser.add_argument("--task-mode", default="general", choices=["general", "code_writer", "code_reviewer", "code_editor", "bug_fixer"], help="Task Mode.")
    
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}/api/chat"

    if args.prompt:
        stream_chat(url, args.model, args.prompt, args.task_mode)
    else:
        # Interactive mode
        print("=== Interactive Local LLM Gateway CLI ===")
        print(f"Targeting: {url} | Model: {args.model}")
        print("Type 'exit' or 'quit' to end session.\n")
        
        while True:
            try:
                prompt = input("\nYou: ")
                if prompt.strip().lower() in ["exit", "quit"]:
                    break
                if not prompt.strip():
                    continue
                stream_chat(url, args.model, prompt, args.task_mode)
            except KeyboardInterrupt:
                print("\nSession ended.")
                break

if __name__ == "__main__":
    main()
