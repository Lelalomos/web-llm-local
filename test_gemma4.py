#!/usr/bin/env python3
import requests
import json
import sys
import time

URL_TAGS = "http://127.0.0.1:11434/api/tags"
URL_CHAT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "gemma4:e2b"

def get_available_model():
    try:
        res = requests.get(URL_TAGS)
        if res.status_code == 200:
            models = [m["name"] for m in res.json().get("models", [])]
            if DEFAULT_MODEL in models:
                return DEFAULT_MODEL
            elif models:
                print(f"[Info] '{DEFAULT_MODEL}' is not fully downloaded yet. Testing with available model: '{models[0]}'")
                return models[0]
    except Exception:
        pass
    return DEFAULT_MODEL

def test_gemma():
    model = get_available_model()
    print(f"\n--- Testing Local LLM Pipeline ({model}) ---")
    
    prompt = "Explain why gravity works in one simple sentence."
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": True
    }
    
    print(f"User: {prompt}\n")
    print(f"Response: ", end="", flush=True)
    
    try:
        start_time = time.time()
        response = requests.post(URL_CHAT, json=payload, stream=True)
        if response.status_code != 200:
            print(f"\nError: Received status code {response.status_code} from Ollama server.")
            print(response.text)
            sys.exit(1)
            
        full_response = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                content = chunk.get("message", {}).get("content", "")
                print(content, end="", flush=True)
                full_response += content
                
        duration = time.time() - start_time
        print(f"\n\n[Success] Response received in {duration:.2f} seconds.")
        return True
        
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to the Ollama server at http://127.0.0.1:11434.")
        print("Please ensure the Ollama server is running by executing: ./setup.sh or ./run_gemma4.sh start")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_gemma()
