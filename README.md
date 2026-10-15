# JyotishKit 🪐

> **Type-Safe, Developer-First Jyotish Knowledge Engine, SDK & REST API**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev)
[![Swiss Ephemeris](https://img.shields.io/badge/SwissEphemeris-2.10-orange.svg)](https://www.astro.com/swisseph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**JyotishKit** is an open, high-precision Vedic astrology engine designed for modern developers and AI systems. It bridges millennia-old astronomical and classical predictive knowledge (Parashari, Jaimini, KP) with modern software engineering: Swiss Ephemeris calculations, Lark AST grammar evaluation, uncertainty window calculus, type-safe Pydantic models, and a production-ready FastAPI REST service.

---

## ⚡ Key Capabilities

* **Astronomical Precision**: Apparent geocentric calculations via Swiss Ephemeris (`pyswisseph`) with bundled high-accuracy ephemeris data.
* **All 16 Divisional Vargas (Shodashavarga)**: D1 (Rashi), D2 (Hora), D3 (Drekkana), D4 (Chaturthamsha), D7 (Saptamsha), D9 (Navamsha), D10 (Dasamsha), D12 (Dvadashamsha), D16 (Shodashamsha), D20 (Vimsamsha), D24 (Siddhamsha), D27 (Saptavimsamsha), D30 (Trimshamsha), D40 (Khavedamsha), D45 (Akshavedamsha), D60 (Shashtiamsha).
* **Multi-School Dasha Systems**: Hierarchical timeline computation for **Vimshottari** (120-year), **Yogini** (36-year), **Chara Dasha** (Jaimini/K.N. Rao), **Narayana Dasha**, and **Kalachakra Dasha**.
* **House Systems & Cusps**: Whole Sign (Parashari), Sripati (Bhava Chalit midpoint shifts), and Placidus KP cusps with 4-level Krishnamurti significators.
* **Ashtakavarga & Shadbala**: Complete Sarvashtakavarga (SAV), Bhinnashtakavarga (BAV), Trikona/Ekadhipatya reductions, and 6-fold Shadbala strengths in Rupas.
* **The AI Ground-Truth Layer**: Deterministic fact-graph and classical sutra citations (BPHS, Phaladeepika, Jaimini Upadesa Sutras) formatted specifically to eliminate LLM hallucinations in AI astrologers and wellness apps.
* **Birth-Time Uncertainty Calculus**: Models facts across a timing uncertainty window (e.g., ±30 seconds) to determine which vargas and cusps remain rock-solid versus sensitive.

---

## 🚀 Quickstart

### 1. Installation

Requires Python 3.12+. Built with [`uv`](https://docs.astral.sh/uv/):

```bash
cd ~/workplace/jyotish-kit

# Sync dependencies and compile Swiss Ephemeris
SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX15.sdk uv sync
```

Alternatively, install via standard pip:
```bash
pip install .
```

---

### 2. Python SDK Example

```python
from jyotish_kit import Jyotish

# Initialize with birth details
chart = Jyotish.create(
    dt_local="2001-10-11T05:57:30",
    lat=29.681312,
    lon=77.010063,
    tz_name="Asia/Kolkata",
    place_name="Karnal, Haryana, India",
    ayanamsa="LAHIRI",
)

# 1. Inspect planetary positions & dignities
planets = chart.get_planets()
print("Moon sign:", planets["Moon"]["sign"])       # Cancer
print("Moon house:", planets["Moon"]["house"])     # 11
print("Moon dignity:", planets["Moon"]["dignity"]) # own

# 2. Check Sarvashtakavarga (SAV) bindus
sav = chart.get_ashtakavarga()["SAV"]
print("11th House SAV bindus:", sav[11])           # 37

# 3. Divisional charts (Navamsha & Dasamsha)
vargas = chart.get_vargas(["D1", "D9", "D10"])
print("D9 Navamsha Mars:", vargas["D9"]["Mars"])   # Scorpio
print("D10 Dasamsha Mars:", vargas["D10"]["Mars"]) # Leo

# 4. Active Vimshottari dasha hierarchy
dashas = chart.get_dashas("vimshottari", depth=2)
for d in dashas[:3]:
    print(f"{'/'.join(d['lords'])}: {d['start'][:10]} -> {d['end'][:10]}")
```

---

### 3. Launching the REST API

Launch the local API server with hot-reloading:

```bash
uv run jyotish-kit serve --port 8000 --reload
```

Interactive OpenAPI documentation is live at:
* Swagger UI: **http://127.0.0.1:8000/docs**
* ReDoc: **http://127.0.0.1:8000/redoc**

---

## 📡 REST API Reference

All requests accept a standard birth coordinate payload:

```json
{
  "dt_local": "2001-10-11T05:57:30",
  "lat": 29.681312,
  "lon": 77.010063,
  "tz_name": "Asia/Kolkata",
  "place_name": "Karnal, Haryana, India",
  "time_uncertainty_min": 0.5,
  "ayanamsa": "LAHIRI"
}
```

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service liveness probe. |
| `POST` | `/v1/chart` | Complete planetary state, Panchanga, Bhavas, Shadbala, and SAV. |
| `POST` | `/v1/vargas` | Divisional charts (D1 to D60). Optionally filter requested vargas. |
| `POST` | `/v1/dashas` | Dasha timelines (`vimshottari`, `yogini`, `chara`, `narayana`, `kalachakra`). |
| `POST` | `/v1/transits` | Gochara for any date, Ashtakavarga kakshya points, and Sade Sati timeline. |
| `POST` | `/v1/timing` | Evaluates activated windows for career, wealth, marriage, travel, property. |
| `POST` | `/v1/ground-truth` | **LLM Context Payload**: Ground-truth facts + cited classical sutras. |
| `POST` | `/v1/report` | Generates complete publication-grade Markdown Kundli dossier. |

#### Example: Compute Chart via cURL
```bash
curl -X POST "http://127.0.0.1:8000/v1/chart" \
     -H "Content-Type: application/json" \
     -d '{
       "dt_local": "2001-10-11T05:57:30",
       "lat": 29.681312,
       "lon": 77.010063,
       "tz_name": "Asia/Kolkata"
     }'
```

---

## 🤖 The AI Ground-Truth Pattern

To prevent LLMs from hallucinating planetary positions or inventing non-existent transits, query `/v1/ground-truth` and inject the verified payload directly into the system prompt:

```python
import json
from jyotish_kit import Jyotish

chart = Jyotish.create("2001-10-11T05:57:30", 29.681312, 77.010063)
context = chart.to_llm_context(topics=["career", "wealth"])

system_prompt = f"""
You are an expert Vedic astrologer. Answer the user's question using ONLY the verified facts below.
Do not hallucinate planetary positions or dasha dates.

### VERIFIED GROUND TRUTH:
{json.dumps(context, indent=2)}
"""
```

---

## 🐳 Docker Deployment

Run the API anywhere with zero local compilation dependencies:

```bash
# Build and run container
docker compose up -d

# Check logs
docker compose logs -f
```

The container packages Python 3.12, compiled Swiss Ephemeris C extensions, and all planetary ephemeris tables on port 8000.

---

## 🧪 Testing

Run the full test suite with Pytest:

```bash
uv run pytest tests/ -v
```

---

## 🏛️ Classical Sources & Conventions

* **Parashari**: *Brihat Parashara Hora Shastra* (R. Santhanam tr.) & *Phaladeepika* (Mantreswara).
* **Jaimini**: *Jaimini Upadesa Sutras* (Adhyayas 1–2).
* **KP**: *Krishnamurti Padhdhati Readers III & IV* (249 sub-lords, 4-level significators).
* **Astronomical Engine**: Swiss Ephemeris (`SEFLG_SWIEPH`, true nodes, apparent geocentric).