from starlette.testclient import TestClient
from jyotish_kit.api.app import app

client = TestClient(app)

SAMPLE_BIRTH = {
    "dt_local": "2001-10-11T05:57:30",
    "lat": 29.681312,
    "lon": 77.010063,
    "tz_name": "Asia/Kolkata",
    "place_name": "Karnal, Haryana, India",
    "time_uncertainty_min": 0.5,
    "ayanamsa": "LAHIRI",
}


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert "JyotishKit API" in res.json()["service"]


def test_compute_chart():
    res = client.post("/v1/chart", json=SAMPLE_BIRTH)
    assert res.status_code == 200
    data = res.json()
    assert "planets" in data
    assert "bhavas" in data
    assert "shadbala" in data
    assert "ashtakavarga" in data
    assert data["planets"]["Moon"]["sign"] == "Cancer"
    assert data["planets"]["Moon"]["house"] == 11


def test_compute_vargas():
    res = client.post("/v1/vargas", json={"birth": SAMPLE_BIRTH, "vargas": ["D1", "D9", "D10"]})
    assert res.status_code == 200
    data = res.json()
    assert "vargas" in data
    assert "D9" in data["vargas"]
    assert data["vargas"]["D9"]["Mars"] == "Scorpio"


def test_compute_dashas():
    res = client.post("/v1/dashas", json={"birth": SAMPLE_BIRTH, "system": "vimshottari", "depth": 2})
    assert res.status_code == 200
    data = res.json()
    assert data["system"] == "vimshottari"
    assert len(data["periods"]) > 0


def test_compute_ground_truth():
    res = client.post("/v1/ground-truth", json={"birth": SAMPLE_BIRTH, "topics": ["career"]})
    assert res.status_code == 200
    data = res.json()
    assert "planets" in data
    assert "judgments" in data
    assert "career" in data["judgments"]


def test_compute_timing():
    res = client.post("/v1/timing", json={"birth": SAMPLE_BIRTH, "topic": "career", "years": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["topic"] == "career"
    assert len(data["windows"]) > 0
