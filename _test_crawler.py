"""Test crawler trigger via API"""

import requests
import time

# Trigger crawl
print("Triggering arxiv crawler...")
resp = requests.post(
    "http://localhost:8000/api/crawler/crawl",
    json={"spider": "arxiv", "max_results": 10},
)
print(f"Response: {resp.status_code}")
print(resp.json())

# Wait and check status
print("\nWaiting 10 seconds...")
time.sleep(10)

resp = requests.get("http://localhost:8000/api/crawler/status")
print(f"\nStatus: {resp.json()}")

# Check articles
resp = requests.get("http://localhost:8000/api/crawler/articles?page=1&page_size=10")
print(f"\nArticles: {resp.json()}")
