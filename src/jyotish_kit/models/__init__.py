from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from jyotish_kit.config import ChartConfig

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
SEVEN = PLANETS[:7]
OUTER = ("Uranus", "Neptune", "Pluto")
SIGNS = ("Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces")
SIGN_LORDS = ("Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter")


class BirthTimeError(ValueError):
    """Local birth time is ambiguous (DST fall-back) or nonexistent (spring-forward)."""


class BirthData(BaseModel):
    dt_local: datetime  # naive wall-clock time at the birthplace
    tz_name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    time_uncertainty_min: float = Field(default=0, ge=0)
    place_name: str = ""
    # Required only when dt_local is ambiguous: 0 = first occurrence (DST), 1 = second.
    fold: int | None = None

    def utc(self, offset_sec: float = 0) -> datetime:
        """UTC instant of the birth (shifted by offset_sec), resolving historical tz/DST."""
        if self.dt_local.tzinfo is not None:
            raise BirthTimeError("dt_local must be naive wall-clock time; give the zone in tz_name")
        z = ZoneInfo(self.tz_name)
        a, b = (self.dt_local.replace(tzinfo=z, fold=f) for f in (0, 1))
        if a.utcoffset() != b.utcoffset():
            roundtrip = a.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)
            if roundtrip != self.dt_local:
                raise BirthTimeError(f"{self.dt_local} does not exist in {self.tz_name} (DST gap)")
            if self.fold is None:
                raise BirthTimeError(
                    f"{self.dt_local} is ambiguous in {self.tz_name}: offsets "
                    f"{a.utcoffset()} (fold=0) and {b.utcoffset()} (fold=1); set fold explicitly")
            a = b if self.fold else a
        return a.astimezone(timezone.utc) + timedelta(seconds=offset_sec)

    def utc_offset(self) -> timedelta:
        return self.utc().astimezone(ZoneInfo(self.tz_name)).utcoffset()


class Body(BaseModel):
    name: str
    lon: float  # sidereal ecliptic longitude, degrees
    lat: float
    speed: float  # deg/day in longitude
    retro: bool
    magnitude: float | None = None
    decl: float | None = None  # true equatorial declination of date, degrees (north +)
    helio_lon: float | None = None  # sidereal heliocentric longitude (Mars..Saturn, Mercury, Venus)

    @property
    def sign(self) -> int:
        return int(self.lon // 30)

    @property
    def deg(self) -> float:
        return self.lon % 30


class Chart(BaseModel):
    birth: BirthData
    config: ChartConfig
    utc: datetime
    jd_ut: float
    ayanamsa: float
    ayanamsa_kp: float  # config.kp_ayanamsa at the same moment
    bodies: dict[str, Body]  # includes "Lagna" (lat/speed 0)
    placidus_cusps: list[float]  # 12 sidereal cusps
    sunrise: datetime  # sunrise beginning the Vedic day containing the birth
    sunset: datetime  # sunset following that sunrise
    next_sunrise: datetime
    is_day: bool
    sun_lon_at_sunrise: float  # sidereal Sun at `sunrise`
    sun_lon_at_next_sunrise: float


class FactKind(StrEnum):
    placement = "placement"
    lordship = "lordship"
    aspect = "aspect"
    conjunction = "conjunction"
    dignity = "dignity"
    relationship = "relationship"
    combustion = "combustion"
    war = "war"
    dasha_period = "dasha_period"
    ashtakavarga = "ashtakavarga"
    karaka = "karaka"
    arudha = "arudha"
    special_lagna = "special_lagna"
    rashi_aspect = "rashi_aspect"
    kp_lords = "kp_lords"
    kp_significator = "kp_significator"
    shadbala = "shadbala"
    avastha = "avastha"
    transit = "transit"
    varshaphal = "varshaphal"
    bhava_bala = "bhava_bala"
    panchanga = "panchanga"
    upagraha = "upagraha"
    functional = "functional"
    exchange = "exchange"
    argala = "argala"
    sensitive = "sensitive"


class Fact(BaseModel):
    id: str
    kind: FactKind
    varga: str = "D1"
    subject: str
    object: str | None = None
    attrs: dict[str, Any] = {}
    # True when the fact holds with identical categorical attrs across the whole birth window.
    stable: bool = True
    # Fraction of window samples in which the fact holds as stated.
    window_fraction: float = 1.0
    # Where the rule or table behind this fact comes from (text, chapter, or convention).
    source: str = ""


class DashaPeriod(BaseModel):
    lords: tuple[str, ...]  # (maha,) / (maha, antar) / (maha, antar, pratyantar)
    start: datetime  # UTC
    end: datetime


class LifeEvent(BaseModel):
    date: date
    end: date | None = None  # last day of the window in which the event happened; None = see precision
    precision: Literal["day", "month", "year"] = "day"  # without `end`: the day, its month, or its year
    domain: str
    description: str = ""
    polarity: int | None = Field(default=None, ge=-2, le=2)  # how it felt: -2 very bad .. +2 very good

    def span(self) -> tuple[date, date]:
        """First and last possible day of the event."""
        if self.end:
            return self.date, self.end
        if self.precision == "year":
            return self.date.replace(month=1, day=1), self.date.replace(month=12, day=31)
        if self.precision == "month":
            nxt = self.date.replace(day=28) + timedelta(days=4)
            return self.date.replace(day=1), nxt - timedelta(days=nxt.day)
        return self.date, self.date


# ---------------------------------------------------------------- rule corpus (Layer 2)

DOMAINS = (
    "self", "health", "longevity", "appearance", "temperament", "wealth", "family", "speech", "education",
    "siblings", "courage", "communication", "mother", "home", "property", "vehicles", "happiness", "children",
    "intelligence", "romance", "enemies", "disease", "debts", "service", "marriage", "spouse", "partnership",
    "inheritance", "occult", "hidden_matters", "fortune", "father", "dharma", "guru", "travel", "career",
    "status", "authority", "fame", "gains", "friends", "losses", "expenditure", "foreign", "moksha",
    "spirituality", "sexuality",
)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=2)
    chapter: int | str
    verse: int | str | None = None
    edition: str = Field(min_length=3)
    paraphrase: str = Field(min_length=10)  # our own wording, never a copied translation
    sanskrit: str | None = None  # public-domain original only
    note: str | None = None  # e.g. "verse number to be confirmed against the edition"


class Effect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domains: list[Literal[DOMAINS]] = Field(min_length=1)  # type: ignore[valid-type]
    polarity: int = Field(ge=-2, le=2)
    themes: list[str] = []


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Z][A-Za-z]*\.[A-Za-z0-9]+\.[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?$")
    name: str | None = None  # e.g. "Gajakesari yoga"
    school: Literal["parashari", "jaimini", "kp", "tajika", "nadi", "lalkitab"]
    source: Source
    condition: str
    varga: str = "D1"
    effect: Effect
    cancels_if: str | None = None
    timing: str | None = None
    classical_strength: Literal["primary", "supporting", "minority_view"]
    tags: list[str] = []
    status: Literal["draft", "verified", "disputed"] = "draft"
    verified_by: str | None = None
