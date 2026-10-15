from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class BirthInput(BaseModel):
    dt_local: datetime = Field(
        ...,
        description="Local ISO-8601 birth timestamp (e.g. 2001-10-11T05:57:30)",
        json_schema_extra={"example": "2001-10-11T05:57:30"},
    )
    lat: float = Field(..., description="Latitude in decimal degrees", json_schema_extra={"example": 29.681312})
    lon: float = Field(..., description="Longitude in decimal degrees", json_schema_extra={"example": 77.010063})
    tz_name: str = Field(
        default="Asia/Kolkata",
        description="IANA Timezone string",
        json_schema_extra={"example": "Asia/Kolkata"},
    )
    place_name: str | None = Field(
        default="Karnal, Haryana, India",
        description="Human readable birth place",
        json_schema_extra={"example": "Karnal, Haryana, India"},
    )
    time_uncertainty_min: float = Field(
        default=0.5,
        description="Birth time uncertainty in minutes (±)",
        json_schema_extra={"example": 0.5},
    )
    ayanamsa: str = Field(
        default="LAHIRI",
        description="Ayanamsa system (LAHIRI, KRISHNAMURTI, TRUE_CITRA, RAMAN, YUKTESHWAR)",
        json_schema_extra={"example": "LAHIRI"},
    )


class ChartResponse(BaseModel):
    subject: dict[str, Any]
    panchanga: dict[str, Any]
    planets: dict[str, Any]
    bhavas: dict[str, Any]
    shadbala: dict[str, Any]
    ashtakavarga: dict[str, Any]


class VargasRequest(BaseModel):
    birth: BirthInput
    vargas: list[str] | None = Field(
        default=None,
        description="List of divisional charts (e.g. ['D1', 'D9', 'D10']). If omitted, returns all 16.",
        json_schema_extra={"example": ["D1", "D9", "D10", "D60"]},
    )


class DashasRequest(BaseModel):
    birth: BirthInput
    system: str = Field(
        default="vimshottari",
        description="Dasha system: vimshottari, yogini, chara, narayana, kalachakra",
        json_schema_extra={"example": "vimshottari"},
    )
    depth: int = Field(default=2, ge=1, le=4, description="Depth of dasha hierarchy (1=Maha, 2=Antar, 3=Pratyantar)")


class TransitsRequest(BaseModel):
    birth: BirthInput
    transit_dt: datetime | None = Field(
        default=None,
        description="Timestamp to compute transits for. Defaults to current moment.",
        json_schema_extra={"example": "2026-10-15T15:30:00"},
    )


class TimingRequest(BaseModel):
    birth: BirthInput
    topic: str = Field(
        default="career",
        description="Life domain: career, wealth, marriage, foreign, property, children, education, health",
        json_schema_extra={"example": "career"},
    )
    years: int = Field(default=5, ge=1, le=20, description="Number of years ahead to evaluate")
    include_drafts: bool = Field(default=True, description="Whether to include draft corpus rules")


class LLMContextRequest(BaseModel):
    birth: BirthInput
    topics: list[str] | None = Field(
        default=["career", "wealth", "fortune", "spirituality"],
        description="Life topics to include cited evidence and school judgments for."
    )


class ReportRequest(BaseModel):
    birth: BirthInput
    format: str = Field(default="markdown", description="Report format (markdown)")
