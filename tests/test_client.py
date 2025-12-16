#!/usr/bin/env python3
"""
Example client for testing Tokamak AI API Server
"""

import requests
import json
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (필요한 경우)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configuration
API_URL = "http://localhost:8000"
API_KEY = "YOUR_API_KEY_HERE"  # Replace with your API key

def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_list_models():
    """Test list models endpoint"""
    print("\n=== Testing List Models ===")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(f"{API_URL}/api/tags", headers=headers)
    
    if response.status_code == 200:
        models = response.json().get("models", [])
        print(f"Found {len(models)} models:")
        for model in models:
            print(f"  - {model['name']}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

def test_generate(prompt: str, model: str = "deepseek-coder:33b", stream: bool = False):
    """Test generate endpoint"""
    print(f"\n=== Testing Generate (stream={stream}) ===")
    print(f"Prompt: {prompt}\n")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": stream
    }
    
    start_time = time.time()
    
    if stream:
        response = requests.post(
            f"{API_URL}/api/generate",
            headers=headers,
            json=data,
            stream=True
        )
        
        print("Response: ", end="", flush=True)
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "response" in chunk:
                    print(chunk["response"], end="", flush=True)
        print()
    else:
        response = requests.post(
            f"{API_URL}/api/generate",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result.get('response', '')}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    
    duration = time.time() - start_time
    print(f"\nDuration: {duration:.2f}s")

def test_chat():
    """Test chat endpoint"""
    print("\n=== Testing Chat API ===")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-coder:33b",
        "messages": [
            {"role": "user", "content": "What is Solidity?"}
        ],
        "stream": False
    }
    
    response = requests.post(
        f"{API_URL}/api/chat",
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        result = response.json()
        message = result.get("message", {})
        print(f"Response: {message.get('content', '')}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

def test_usage():
    """Test usage endpoint"""
    print("\n=== Testing Usage Stats ===")
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(f"{API_URL}/usage/me", headers=headers)
    
    if response.status_code == 200:
        usage = response.json()
        print(f"Username: {usage['username']}")
        print(f"Rate Limit: {usage['rate_limit']}")
        print(f"Current Usage: {usage['current_hour_usage']}")
        print(f"Remaining: {usage['remaining']}")
        print(f"\nRecent Requests: {len(usage['recent_requests'])}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

def test_rate_limit():
    """Test rate limiting"""
    print("\n=== Testing Rate Limit ===")
    print("Sending 5 rapid requests...")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-coder:33b",
        "prompt": "Hello",
        "stream": False
    }
    
    for i in range(5):
        response = requests.post(
            f"{API_URL}/api/generate",
            headers=headers,
            json=data
        )
        print(f"Request {i+1}: Status {response.status_code}")
        
        if response.status_code == 429:
            print("Rate limit hit!")
            print(response.json())
            break

def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("Error: Please set your API_KEY in the script")
        sys.exit(1)
    
    print("Tokamak AI API Server - Test Client")
    print("=" * 50)
    
    # Run tests
    try:
        test_health()
        test_list_models()
        test_generate("Write a simple Python function", stream=False)
        test_generate("Explain async/await in Python", stream=True)
        test_chat()
        test_usage()
        # test_rate_limit()  # Uncomment to test rate limiting
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to API server")
        print(f"Make sure the server is running at {API_URL}")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
