"""Measure real /ask latency, including the configured LLM call.

Start the backend with LLM_PROVIDER=groq and a valid GROQ_API_KEY first, then:
    python scripts/benchmark_live.py

Optional environment variables: COMMUTEIQ_API_URL, BENCHMARK_REQUESTS,
BENCHMARK_QUESTION, BENCHMARK_COMPANY, BENCHMARK_EMPLOYEE.
"""
import json
import os
import statistics
import time
import urllib.error
import urllib.request

BASE = os.getenv("COMMUTEIQ_API_URL", "http://127.0.0.1:8000").rstrip("/")
COUNT = max(5, int(os.getenv("BENCHMARK_REQUESTS", "20")))
COMPANY = os.getenv("BENCHMARK_COMPANY", "technova")
EMPLOYEE = os.getenv("BENCHMARK_EMPLOYEE", "benchmark-employee")
QUESTION = os.getenv("BENCHMARK_QUESTION", "What is the minimum office attendance for standard commute eligibility?")


def post(path, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read().decode())


def percentile(values, p):
    values = sorted(values)
    if not values:
        return None
    return round(values[min(len(values) - 1, int((len(values) - 1) * p + 0.9999))], 1)


def main():
    _, token_response = post("/auth/demo-token", {"employee_id": EMPLOYEE, "company_id": COMPANY})
    token = token_response["access_token"]
    samples, failures = [], []
    # One warm-up request is excluded from the measured sample.
    post("/ask", {"question": QUESTION}, token)
    for index in range(COUNT):
        started = time.perf_counter()
        try:
            status, body = post("/ask", {"question": QUESTION}, token)
            elapsed = (time.perf_counter() - started) * 1000
            samples.append(elapsed)
            if status != 200 or not body.get("answer"):
                failures.append({"request": index + 1, "status": status, "error": "empty or unsuccessful response"})
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            elapsed = (time.perf_counter() - started) * 1000
            failures.append({"request": index + 1, "latency_ms": round(elapsed, 1), "error": str(exc)})
    report = {
        "endpoint": BASE + "/ask", "company": COMPANY, "requests": COUNT,
        "successful_requests": len(samples), "failures": failures,
        "latency_ms": {"p50": percentile(samples, .50), "p95": percentile(samples, .95),
                       "max": round(max(samples), 1) if samples else None},
        "target_p95_ms": 3000,
        "target_met": bool(samples) and len(samples) == COUNT and percentile(samples, .95) <= 3000,
        "includes": "HTTP /ask, retrieval, reranking and configured LLM call; one warm-up excluded",
        "warning": "Run with LLM_PROVIDER=groq and a real key. This result applies only to this machine, provider, model and network conditions.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
