# app/cr_client.py
import os, requests

BASE = "https://api.coderabbit.ai/api/v1"
KEY = os.environ.get("CODERABBIT_API_KEY")

def fetch_report(from_date: str, to_date: str) -> dict:
    if not KEY:
        raise RuntimeError("CODERABBIT_API_KEY not set")
    r = requests.post(
        f"{BASE}/report.generate",
        headers={"x-coderabbitai-api-key": KEY, "content-type": "application/json"},
        json={"from": from_date, "to": to_date},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()
