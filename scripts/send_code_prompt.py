#!/usr/bin/env python3
import argparse
import json
import sys

import requests


DEFAULT_PROMPT = "Write a Python program that calculates the sum, average, minimum, and maximum of a list of numbers."


def parse_args():
    parser = argparse.ArgumentParser(description="Send a coding prompt to the local model gateway.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/chat", help="Gateway chat endpoint")
    parser.add_argument("--model", default="gemma4:e2b", help="Model name")
    parser.add_argument("--task-mode", default="code_writer", choices=["general", "code_writer", "code_reviewer", "code_editor", "bug_fixer"], help="Coding task mode")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt text")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "stream": False,
        "web_search_mode": "off",
        "task_mode": args.task_mode,
    }

    response = requests.post(args.url, json=payload, timeout=180)
    response.raise_for_status()
    body = response.json()
    message = body.get("message", {})
    content = message.get("content", "")
    if not content:
        thinking = message.get("thinking", "")
        content = thinking
    sys.stdout.write(content.strip() + "\n")


if __name__ == "__main__":
    main()
