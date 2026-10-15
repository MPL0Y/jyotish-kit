"""
Example 03: Calling the JyotishKit FastAPI Service over HTTP.
Make sure the API server is running (`jyotish-kit serve` or `uvicorn jyotish_kit.api.app:app`).
"""

import httpx

API_BASE = "http://127.0.0.1:8000"

payload = {
    "dt_local": "2001-10-11T05:57:30",
    "lat": 29.681312,
    "lon": 77.010063,
    "tz_name": "Asia/Kolkata",
    "place_name": "Karnal, Haryana, India",
    "ayanamsa": "LAHIRI",
}

try:
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        # 1. Health check
        health = client.get("/health").json()
        print("API Health:", health)

        # 2. Get Chart & SAV
        chart_res = client.post("/v1/chart", json=payload).json()
        moon = chart_res["planets"]["Moon"]
        print(f"Moon: {moon['sign']} (House {moon['house']})")
        print("House 11 SAV Bindus:", chart_res["ashtakavarga"]["SAV"]["11"])

        # 3. Check Career Timing Windows
        timing_res = client.post(
            "/v1/timing",
            json={"birth": payload, "topic": "career", "years": 5},
        ).json()
        print("\n=== TOP CAREER ACTIVATION WINDOWS ===")
        for w in timing_res["windows"][:3]:
            print(f"{w['start'][:10]} -> {w['end'][:10]} | Score: {w['score']:<5} | Lords: {'/'.join(w['lords'])}")

except httpx.ConnectError:
    print(f"Could not connect to {API_BASE}. Start the server with `jyotish-kit serve` first.")
