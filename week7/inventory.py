#!/usr/bin/env python3
"""Week 7 lab, Steps 5 and 6: read EVERY device from the lab API, however it misbehaves.

Run it in the client container:
    # Set LAB_USERNAME and LAB_PASSWORD in your environment first.
    python3 inventory.py

It writes devices.json and prints how many devices each site has. It follows the API's next links and handles rate limits and token expiry.
"""
import json
import os
import random
import sys
import time
from collections import Counter
from urllib.parse import urlsplit

import requests

API = os.environ.get("LAB_API_URL", "http://api:8000")


class Client:
    """A logged-in session with the lab API."""

    def __init__(self):
        self.token = None
        self.requests = 0  # how many HTTP requests this client sent, retries included

    def login(self):
        """Get a fresh token, with the username and password from the environment."""
        try:
            user, password = os.environ["LAB_USERNAME"], os.environ["LAB_PASSWORD"]
        except KeyError:
            sys.exit("Set LAB_USERNAME and LAB_PASSWORD in the environment first.")
        self.requests += 1
        r = requests.post(f"{API}/api/v1/auth/token", json={"username": user, "password": password}, timeout=5)
        r.raise_for_status()
        self.token = r.json()["token"]
        print(f"logged in as {user}")

    def request(self, method, url, *, body=None, key=None):
        """Send one operation. A POST needs the same key for every retry."""
        if method not in {"GET", "PUT", "DELETE"} and not (method == "POST" and key):
            raise ValueError(f"Cannot retry an unkeyed {method}")
        origin, target = urlsplit(API), urlsplit(url)
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
            raise ValueError("API URL points to a different server")
        if self.token is None:
            self.login()

        failures = rate_limits = refreshes = 0
        while True:
            headers = {"Authorization": f"Bearer {self.token}"}
            if key:
                headers["Idempotency-Key"] = key
            self.requests += 1
            try:
                response = requests.request(
                    method, url, json=body, headers=headers, timeout=5, allow_redirects=False
                )
            except (requests.ConnectionError, requests.Timeout) as error:
                failure = type(error).__name__
                failures += 1
                if failures == 6:
                    raise
            else:
                if response.status_code == 401 and refreshes < 3:
                    print("401: refreshing token and retrying the same request")
                    self.login()
                    refreshes += 1
                    continue
                if response.status_code == 429:
                    rate_limits += 1
                    if rate_limits == 6:
                        response.raise_for_status()
                    wait = int(response.headers.get("Retry-After", "1"))
                    print(f"429: waiting {wait}s before retry")
                    time.sleep(wait)
                    continue
                if response.status_code == 404 and method == "DELETE":
                    return response  # A previous attempt may already have removed it.
                if response.status_code != 503:
                    response.raise_for_status()
                    if not 200 <= response.status_code < 300:
                        raise ValueError(f"Unexpected HTTP status {response.status_code}")
                    return response
                failure = "503"
                failures += 1
                if failures == 6:
                    response.raise_for_status()

            wait = 2 ** (failures - 1) + random.uniform(0, 0.25)
            print(f"{failure}: {method} {target.path}, waiting {wait:.2f}s before retry")
            time.sleep(wait)

    def get_page(self, url):
        """Read one page with the same retry rules as the sync client."""
        return self.request("GET", url)

    def get_all(self, url):
        """Collect every page and read X-Total-Count if the API provides it."""
        items, total = [], None
        first = True
        while url is not None:
            response = self.get_page(url)
            if first:
                count = response.headers.get("X-Total-Count")
                total = int(count) if count is not None else None
                first = False
            page = response.json()
            items.extend(page["items"])
            url = page["next"]
        return items, total


def main():
    c = Client()
    devices, total = c.get_all(f"{API}/api/v1/devices?limit=10")
    if not devices:
        sys.exit("The inventory is empty.")
    with open("devices.json", "w") as f:
        json.dump(devices, f, indent=2)
    print(f"{len(devices)} devices read (the API says {total}), in {c.requests} requests; saved devices.json")
    for site, n in sorted(Counter(d["site"] for d in devices).items()):
        print(f"  {site}: {n}")
    if total is None or len(devices) != int(total):
        sys.exit("The count doesn't match X-Total-Count: some devices are missing.")


if __name__ == "__main__":
    main()
