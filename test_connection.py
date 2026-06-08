#!/usr/bin/env python3
import socket
import requests
import json
import sys

def check_port(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False

def test_endpoint(url, desc):
    print(f"\nTesting {desc} at {url}...")
    try:
        res = requests.get(url, headers={"Origin": "http://127.0.0.1:8002"}, timeout=3)
        print(f"  Status Code: {res.status_code}")
        print(f"  CORS Headers (Access-Control-Allow-Origin): {res.headers.get('Access-Control-Allow-Origin', 'None')}")
        if res.status_code == 200:
            try:
                data = res.json()
                models = [m.get("name") for m in data.get("models", [])] if "models" in data else None
                if models is not None:
                    print(f"  Available Models: {models}")
                else:
                    print(f"  Response Preview: {str(data)[:100]}")
            except Exception:
                print(f"  Response Text: {res.text[:100]}")
            return True
        else:
            print(f"  Error Detail: {res.text[:200]}")
            return False
    except Exception as e:
        print(f"  Failed to query endpoint: {e}")
        return False

def main():
    print("=== Diagnostic Connection Test ===")
    
    ports = {
        8000: "Docker Nginx Proxy",
        8001: "Standalone Gateway Backend",
        11434: "Ollama Service"
    }
    
    for port, name in ports.items():
        open_status = check_port("127.0.0.1", port)
        print(f"Port {port} ({name}): {'OPEN' if open_status else 'CLOSED'}")

    # Test Nginx Gateway
    if check_port("127.0.0.1", 8000):
        test_endpoint("http://127.0.0.1:8000/api/config", "Docker Nginx Config Endpoint")
        test_endpoint("http://127.0.0.1:8000/api/tags", "Docker Nginx Model Tags Endpoint")
        
    # Test Standalone Gateway
    if check_port("127.0.0.1", 8001):
        test_endpoint("http://127.0.0.1:8001/api/config", "Standalone Gateway Config Endpoint")
        test_endpoint("http://127.0.0.1:8001/api/tags", "Standalone Gateway Model Tags Endpoint")

    # Test Ollama Direct
    if check_port("127.0.0.1", 11434):
        test_endpoint("http://127.0.0.1:11434/api/tags", "Ollama Direct Tags Endpoint")

if __name__ == "__main__":
    main()
