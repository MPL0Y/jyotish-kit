"""Layer 0: astronomical computation via Swiss Ephemeris. No interpretation here."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import swisseph as swe

from jyotish_kit.config import ChartConfig
from jyotish_kit.models import OUTER, BirthData, Body, Chart

EPHE_PATH = Path(__file__).parent / "data"
swe.set_ephe_path(str(EPHE_PATH))

_IDS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
        "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO}
_J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)


class EphemerisError(RuntimeError):
    pass


def jd_from_utc(t: datetime) -> float:
    return 2451545.0 + (t - _J2000).total_seconds() / 86400


def utc_from_jd(jd: float) -> datetime:
    return _J2000 + timedelta(days=jd - 2451545.0)


def _calc(jd: float, pid: int, flags: int) -> tuple:
    xx, ret = swe.calc_ut(jd, pid, flags)
    if pid not in (swe.TRUE_NODE, swe.MEAN_NODE) and not ret & swe.FLG_SWIEPH:
        # swe silently falls back to Moshier when .se1 files are missing; refuse that.
        raise EphemerisError(f"Swiss Ephemeris files not used for body {pid} (flags {ret}); check {EPHE_PATH}")
    return xx


def _sun_event(jd: float, birth: BirthData, cfg: ChartConfig, rise: bool) -> float:
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    if cfg.sunrise == "hindu":
        flag |= swe.BIT_HINDU_RISING
    res, tret = swe.rise_trans(jd, swe.SUN, flag, (birth.lon, birth.lat, 0), 0, 0, swe.FLG_SWIEPH)
    if res != 0:
        raise EphemerisError("Sun does not rise/set on this date at this latitude")
    return tret[0]


def bodies_at(jd: float, cfg: ChartConfig) -> dict[str, Body]:
    """Sidereal positions of the grahas (and outer planets if configured) at a Julian day (UT)."""
    swe.set_sid_mode(getattr(swe, f"SIDM_{cfg.ayanamsa}"))
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    names = list(_IDS)[:7] + (list(OUTER) if cfg.include_outer else [])
    bodies = {}
    for n in names:
        xx = _calc(jd, _IDS[n], flags)
        mag = swe.pheno_ut(jd, _IDS[n], swe.FLG_SWIEPH)[4] if n not in ("Sun", "Moon") else None
        decl = _calc(jd, _IDS[n], swe.FLG_SWIEPH | swe.FLG_EQUATORIAL)[1]
        helio = _calc(jd, _IDS[n], flags | swe.FLG_HELCTR)[0] if n not in ("Sun", "Moon") else None
        bodies[n] = Body(name=n, lon=xx[0], lat=xx[1], speed=xx[3], retro=xx[3] < 0, magnitude=mag,
                         decl=decl, helio_lon=helio)
    node = _calc(jd, swe.TRUE_NODE if cfg.node == "true" else swe.MEAN_NODE, flags)
    bodies["Rahu"] = Body(name="Rahu", lon=node[0], lat=0, speed=node[3], retro=node[3] < 0)
    bodies["Ketu"] = Body(name="Ketu", lon=(node[0] + 180) % 360, lat=0, speed=node[3], retro=node[3] < 0)
    return bodies


def lagna_at(jd: float, lat: float, lon: float, cfg: ChartConfig) -> float:
    """Sidereal ascendant at a Julian day (UT) for a place."""
    swe.set_sid_mode(getattr(swe, f"SIDM_{cfg.ayanamsa}"))
    return swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)[1][0]


def compute(birth: BirthData, cfg: ChartConfig, offset_sec: float = 0) -> Chart:
    utc = birth.utc(offset_sec)
    jd = jd_from_utc(utc)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    bodies = bodies_at(jd, cfg)

    cusps, ascmc = swe.houses_ex(jd, birth.lat, birth.lon, b"P", swe.FLG_SIDEREAL)
    bodies["Lagna"] = Body(name="Lagna", lon=ascmc[0], lat=0, speed=0, retro=False)

    ayanamsa = swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]
    swe.set_sid_mode(getattr(swe, f"SIDM_{cfg.kp_ayanamsa}"))
    ayanamsa_kp = swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]
    swe.set_sid_mode(getattr(swe, f"SIDM_{cfg.ayanamsa}"))

    next_rise = _sun_event(jd, birth, cfg, True)
    next_set = _sun_event(jd, birth, cfg, False)
    sunrise = _sun_event(next_rise - 1.5, birth, cfg, True)  # the rise ~1 day before next_rise
    sunset = _sun_event(sunrise, birth, cfg, False)

    return Chart(
        birth=birth, config=cfg, utc=utc, jd_ut=jd,
        ayanamsa=ayanamsa, ayanamsa_kp=ayanamsa_kp,
        bodies=bodies, placidus_cusps=list(cusps[:12]),
        sunrise=utc_from_jd(sunrise), sunset=utc_from_jd(sunset),
        next_sunrise=utc_from_jd(next_rise), is_day=next_set < next_rise,
        sun_lon_at_sunrise=_calc(sunrise, swe.SUN, flags)[0],
        sun_lon_at_next_sunrise=_calc(next_rise, swe.SUN, flags)[0],
    )
