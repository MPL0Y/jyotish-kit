from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from jyotish_kit import __version__
from jyotish_kit.api.schemas import (
    BirthInput,
    ChartResponse,
    DashasRequest,
    LLMContextRequest,
    ReportRequest,
    TimingRequest,
    TransitsRequest,
    VargasRequest,
)
from jyotish_kit.core import Jyotish

app = FastAPI(
    title="JyotishKit API",
    description=(
        "Type-safe, developer-first REST API for Vedic Astrometry, Divisional Vargas, "
        "Dasha Timelines, Ashtakavarga, and Cited Synthesis Rule Evaluation."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _init_jyotish(b: BirthInput) -> Jyotish:
    return Jyotish.create(
        dt_local=b.dt_local,
        lat=b.lat,
        lon=b.lon,
        tz_name=b.tz_name,
        place_name=b.place_name,
        time_uncertainty_min=b.time_uncertainty_min,
        ayanamsa=b.ayanamsa,
    )


@app.get("/", tags=["General"])
def root() -> dict[str, Any]:
    """Root metadata and service health status."""
    return {
        "service": "JyotishKit API",
        "version": __version__,
        "documentation": "/docs",
        "description": "Developer-first Vedic Astrometry, Dasha, and Rule-Synthesis Engine",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health", tags=["General"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "healthy"}


@app.post("/v1/chart", response_model=ChartResponse, tags=["Calculations"])
def compute_chart(birth: BirthInput) -> dict[str, Any]:
    """
    Computes complete natal chart state:
    - Graha longitudes, speeds, nakshatras, padas, dignities, baladi avasthas
    - Whole-sign and Bhava Chalit (Sripati) house placements
    - Sarvashtakavarga (SAV) and Bhinnashtakavarga (BAV) bindus
    - 6-fold Shadbala strengths in Rupas
    - 5 limbs of Panchanga (Tithi, Vara, Nakshatra, Yoga, Karana)
    """
    try:
        j = _init_jyotish(birth)
        return {
            "subject": {
                "place_name": birth.place_name,
                "dt_local": birth.dt_local.isoformat(),
                "ayanamsa": birth.ayanamsa,
                "uncertainty_min": birth.time_uncertainty_min,
            },
            "panchanga": j.get_panchanga(),
            "planets": j.get_planets(),
            "bhavas": j.get_bhavas(),
            "shadbala": j.get_shadbala(),
            "ashtakavarga": j.get_ashtakavarga(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/vargas", tags=["Calculations"])
def compute_vargas(req: VargasRequest) -> dict[str, Any]:
    """
    Returns planetary sign placements across the 16 classical Parashari
    divisional charts (Shodashavarga): D1, D2, D3, D4, D7, D9, D10, D12,
    D16, D20, D24, D27, D30, D40, D45, D60.
    """
    try:
        j = _init_jyotish(req.birth)
        return {"vargas": j.get_vargas(req.vargas)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/dashas", tags=["Calculations"])
def compute_dashas(req: DashasRequest) -> dict[str, Any]:
    """
    Computes hierarchical dasha timelines with start and end timestamps.
    Supported systems:
    - `vimshottari`: Nakshatra-based 120-year cycle (Parashari)
    - `yogini`: 8-goddess cycle (36 years)
    - `chara`: Jaimini sign-based dasha (K.N. Rao)
    - `narayana`: Rashi progression dasha (P.V.R. Narasimha Rao)
    - `kalachakra`: Lunar constellation progression cycle
    """
    try:
        j = _init_jyotish(req.birth)
        periods = j.get_dashas(system=req.system, depth=req.depth)
        return {
            "system": req.system,
            "depth": req.depth,
            "count": len(periods),
            "periods": periods,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/transits", tags=["Calculations"])
def compute_transits(req: TransitsRequest) -> dict[str, Any]:
    """
    Calculates Gochara (transits) for any date relative to the natal Lagna and Moon:
    - Planetary transit houses and signs
    - Ashtakavarga Kakshya bindus for active transits
    - 15-year Sade Sati timeline (rising, peak, setting phases)
    """
    try:
        j = _init_jyotish(req.birth)
        return j.get_transits(req.transit_dt)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/timing", tags=["Synthesis & Predictions"])
def compute_timing(req: TimingRequest) -> dict[str, Any]:
    """
    Identifies top 3-5 activated time windows for a specific life domain
    (career, wealth, marriage, foreign travel, property, education) based on
    multi-school dasha activations, Jupiter-Saturn double transits, and rule drivers.
    """
    try:
        j = _init_jyotish(req.birth)
        windows = j.get_timing(topic=req.topic, years=req.years, drafts=req.include_drafts)
        return {
            "topic": req.topic,
            "years": req.years,
            "windows": windows,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/ground-truth", tags=["AI & Agents"])
def get_ground_truth_context(req: LLMContextRequest) -> dict[str, Any]:
    """
    **The AI Ground-Truth Endpoint**:
    Generates a deterministic JSON payload containing verified astrometric facts,
    planetary strengths, and rule citations for direct injection into LLM system prompts.
    Eliminates hallucination in AI astrologers, chatbots, and wellness applications.
    """
    try:
        j = _init_jyotish(req.birth)
        return j.to_llm_context(req.topics)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/report", response_class=PlainTextResponse, tags=["Reports"])
def generate_report(req: ReportRequest) -> str:
    """
    Generates a full, comprehensive Markdown Kundli dossier including
    birth data basis, panchanga, grahas, bhavas, vargas, special points,
    dashas, gochara, annual varshaphal, and classical source citations.
    """
    try:
        j = _init_jyotish(req.birth)
        return j.generate_report()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
