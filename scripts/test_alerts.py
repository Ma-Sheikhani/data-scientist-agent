#!/usr/bin/env python3
"""Automatically test all Prometheus alerts by triggering their conditions."""

import subprocess
import sys
import time

import requests

PROM_URL = "http://localhost:9090"
API_URL = "http://localhost:8000"
COMPOSE_CMD = [
    "docker",
    "compose",
    "-f",
    "deployments/docker-compose/docker-compose.yml",
]


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def prom_query(query):
    """Run an instant Prometheus query."""
    resp = requests.get(f"{PROM_URL}/api/v1/query", params={"query": query})
    resp.raise_for_status()
    return resp.json()["data"]["result"]


def prom_alerts():
    """Fetch all current alerts."""
    resp = requests.get(f"{PROM_URL}/api/v1/alerts")
    resp.raise_for_status()
    return resp.json()["data"]["alerts"]


def alert_state(name):
    """Return state of a specific alert ('inactive', 'pending', 'firing'), or None if not found."""
    for a in prom_alerts():
        if a["labels"]["alertname"] == name:
            return a["state"]
    return None


def wait_for_alert(name, target_state="firing", timeout=300):
    """Poll until alert reaches target state."""
    start = time.time()
    while time.time() - start < timeout:
        state = alert_state(name)
        if state == target_state:
            return True
        print(f"   ... {name} is {state}")
        time.sleep(10)
    return False


# -------------------------------------------------------------------
# Test 1: CeleryWorkerDown
# -------------------------------------------------------------------
def test_worker_down():
    print("\n=== Test: CeleryWorkerDown ===")
    # Stop beat
    subprocess.run(COMPOSE_CMD + ["stop", "beat"], check=True)
    print("Beat stopped. Waiting for alert to fire...")
    ok = wait_for_alert("CeleryWorkerDown", timeout=300)
    # Restart beat
    subprocess.run(COMPOSE_CMD + ["start", "beat"], check=True)
    time.sleep(5)
    if ok:
        print("PASS: CeleryWorkerDown fired correctly.")
    else:
        print("FAIL: CeleryWorkerDown did not fire within timeout.")
        return False
    return True


# -------------------------------------------------------------------
# Test 2: HighAPIErrorRate
# -------------------------------------------------------------------
def test_api_error_rate():
    print("\n=== Test: HighAPIErrorRate ===")
    # Generate a burst of 500 errors
    for _ in range(30):
        try:
            requests.get(f"{API_URL}/test-trigger-500", timeout=5)
        except Exception:
            pass  # expected 500
    # Give Prometheus time to scrape (15s interval)
    print("Sent 500 errors. Waiting for alert...")
    time.sleep(30)  # ensure at least one scrape cycle
    ok = wait_for_alert("HighAPIErrorRate", timeout=180)
    if ok:
        print("PASS: HighAPIErrorRate fired correctly.")
    else:
        print("FAIL: HighAPIErrorRate did not fire within timeout.")
        return False
    return True


# -------------------------------------------------------------------
# Test 3: HighJobFailureRate
# -------------------------------------------------------------------
# def test_job_failure_rate():
#     print("\n=== Test: HighJobFailureRate ===")
#     # We need an auth token. Register & login quickly.
#     email = f"testalert{int(time.time())}@test.com"
#     password = "testpass"
#     reg_resp = requests.post(f"{API_URL}/auth/register",
#                              json={"email": email, "password": password})
#     if reg_resp.status_code != 201:
#         print("   Register failed, maybe already exists. Trying login anyway.")
#     token_resp = requests.post(f"{API_URL}/auth/token",
#                             json={"email": email, "password": password})
#     token_resp.raise_for_status()
#     token = token_resp.json()["access_token"]
#     headers = {"Authorization": f"Bearer {token}"}

#     # Submit several failing jobs (invalid CSV)
#     for i in range(5):
#         files = {"file": ("bad.csv", b"not,a,csv\n1,2,3", "text/csv")}
#         data = {"question": "crash test"}
#         resp = requests.post(f"{API_URL}/v1/analyze",
#                              files=files, data=data, headers=headers)
#         print(f"   Submitted failing job {i+1}: {resp.status_code}")

#     print("Waiting for alert (may take up to 5 min)...")
#     ok = wait_for_alert("HighJobFailureRate", timeout=360)
#     if ok:
#         print("PASS: HighJobFailureRate fired correctly.")
#     else:
#         print("FAIL: HighJobFailureRate did not fire within timeout.")
#         return False
#     return True

# -------------------------------------------------------------------
# Test 4: HighSandboxErrorRate (partial, as it requires actual agent run)
# -------------------------------------------------------------------
# def test_sandbox_error_rate():
#     print("\n=== Test: HighSandboxErrorRate ===")
#     print("Skipping – requires submitting many analysis jobs that cause sandbox errors.")
#     print("To test manually: upload a CSV with mismatched column names repeatedly.")
#     return True  # not a failure

# -------------------------------------------------------------------
if __name__ == "__main__":
    print("Prometheus Alert Auto-Tester")
    print("============================")
    all_pass = True

    # Run tests in order
    all_pass &= test_worker_down()
    all_pass &= test_api_error_rate()
    # all_pass &= test_job_failure_rate()
    # all_pass &= test_sandbox_error_rate()

    print("\n============================")
    if all_pass:
        print("All tests passed (or skipped).")
        sys.exit(0)
    else:
        print("Some tests failed.")
        sys.exit(1)
