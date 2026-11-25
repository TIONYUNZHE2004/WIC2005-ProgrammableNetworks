#!/usr/bin/env python3
"""Week 7 Step 4: use one key for one ACL change and all its retries."""
import os
import sys
import time
import uuid

import requests

API = os.environ.get("LAB_API_URL", "http://api:8000")
TOKEN = os.environ["LAB_API_TOKEN"]  # export LAB_API_TOKEN=... first; never write it in this file

if len(sys.argv) != 2 or not sys.argv[1].isdigit() or len(sys.argv[1]) != 4:
    sys.exit("usage: python3 retry_safe.py <last 4 digits of your student ID>")
NN = int(sys.argv[1][2:])

ENTRY = {
    "action": "deny",
    "src": f"10.{NN}.30.0/24",
    "dst": f"10.{NN}.20.0/24",
    "protocol": "tcp",
    "port": 22,
    "description": "guests may not SSH to servers",
}
# A new run requests a new entry. Retries within this run reuse the key.
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Idempotency-Key": str(uuid.uuid4()),
}

for attempt in range(1, 6):
    try:
        r = requests.post(f"{API}/api/v1/acl/entries", json=ENTRY, headers=HEADERS, timeout=5)
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"attempt {attempt}: no response ({type(e).__name__}) — trying again")
        time.sleep(1)
        continue
    if r.status_code in (429, 503):
        wait = int(r.headers.get("Retry-After", "1"))
        print(f"attempt {attempt}: {r.status_code} — waiting {wait}s")
        time.sleep(wait)
        continue
    r.raise_for_status()
    print(f"attempt {attempt}: {r.status_code} {r.reason}: {r.json()}")
    if r.headers.get("Idempotent-Replayed") == "true":
        print("Idempotent-Replayed: true")
    break
else:
    sys.exit("gave up after 5 attempts")
