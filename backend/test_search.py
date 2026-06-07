#!/usr/bin/env python3
import sys
import os
import requests
import json
import time

from search_service import execute_web_search
from ollama_options import apply_gpu_defaults

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

def get_available_models():
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if res.status_code == 200:
            return [m["name"] for m in res.json().get("models", [])]
    except Exception:
        pass
    return []

def main():
    print("=== Local LLM Search Script Test Tool ===")
    
    # Get user query
    query = input("\nEnter search query (e.g. 'SET index Thailand stock news'): ").strip()
    if not query:
        print("Query cannot be empty.")
        return
        
    print("\n--- 1. Executing Web Search ---")
    start_time = time.time()
    search_context, search_results = execute_web_search(query)
    duration = time.time() - start_time
    
    print(f"\n[Search Completed in {duration:.2f} seconds]")
    
    if not search_results:
        print("No search results found.")
    else:
        print(f"\nFound {len(search_results)} search results:")
        for idx, res in enumerate(search_results, 1):
            print(f"\n[{idx}] {res['title']}")
            print(f"    URL:  {res['href']}")
            print(f"    Body: {res['body']}")
            
    print("\n--- 2. Injected System Prompt Context Preview ---")
    print(search_context[:1000] + "\n... (truncated for display) ..." if len(search_context) > 1000 else search_context)
    
    # Ask if user wants to test with local LLM
    models = get_available_models()
    if not models:
        print("\n[Notice] No local Ollama service detected or no models installed. Skipping LLM response test.")
        return
        
    print("\nAvailable local models:")
    for idx, model in enumerate(models, 1):
        print(f"  {idx}. {model}")
    
    try:
        model_choice = input(f"Choose model [1-{len(models)}] (default: 1): ").strip()
        if not model_choice:
            selected_model = models[0]
        else:
            selected_model = models[int(model_choice) - 1]
    except (ValueError, IndexError):
        selected_model = models[0]
        
    print(f"\nTesting with model: {selected_model}")
    
    # Build payload
    search_system_prompt = f"Use the following Web Search results to help answer the user's question:\n\n{search_context}\n\nProvide citations for the URLs when referencing them."
    
    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": search_system_prompt},
            {"role": "user", "content": query}
        ],
        "stream": True
    }
    
    apply_gpu_defaults(payload)
    print(f"[Info] Ollama options: {payload.get('options', {})}")
    
    print(f"\nResponse: ", end="", flush=True)
    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=120)
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    content = chunk.get("message", {}).get("content", "")
                    print(content, end="", flush=True)
            print()
        else:
            print(f"\nError: Ollama returned status code {response.status_code}")
    except Exception as e:
        print(f"\nError connecting to Ollama: {e}")

if __name__ == "__main__":
    main()
