#!/usr/bin/env python3
import argparse
import json
import sys

import requests


def parse_args():
    parser = argparse.ArgumentParser(description="Call the local /api/chat endpoint with the correct project payload.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/chat", help="Gateway chat endpoint")
    parser.add_argument("--model", default="gemma4:e2b", help="Model name")
    parser.add_argument("--task-mode", default="general", choices=["general", "code_writer", "code_reviewer", "code_editor", "bug_fixer"], help="Task mode")
    parser.add_argument("--web-search-mode", default="off", choices=["off", "auto", "on"], help="Web search mode")
    parser.add_argument("--stream", action="store_true", help="Request streaming response")
    parser.add_argument("prompt", nargs="?", default="Write a short Python function that adds two numbers.", help="Prompt text")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "stream": args.stream,
        "web_search_mode": args.web_search_mode,
        "task_mode": args.task_mode,
    }

    response = requests.post(args.url, json=payload, timeout=180, stream=args.stream)
    response.raise_for_status()

    if args.stream:
        for line in response.iter_lines():
            if not line:
                continue
            sys.stdout.write(line.decode("utf-8") + "\n")
        return

    body = response.json()
    print(json.dumps(body, indent=2))


if __name__ == "__main__":
    main()
