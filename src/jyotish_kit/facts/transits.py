"""Gochara (transits) against a natal chart: houses from Lagna and Moon, ashtakavarga support of the
transited sign, Sade Sati, and the Jupiter-Saturn double transit (K.N. Rao: a house is activated when
both transit Jupiter and Saturn occupy or graha-aspect it).
"""

from datetime import datetime, timedelta

from jyotish_kit.ephemeris.engine import bodies_at, jd_from_utc
from jyotish_kit.facts.builders.ashtakavarga import bav
from jyotish_kit.facts.builders.aspects import aspect_distances
from jyotish_kit.facts.builders.nakshatra import NAKSHATRAS, nakshatra
from jyotish_kit.facts.builders.placements import house
from jyotish_kit.models import PLANETS, SEVEN, SIGNS, Chart, Fact, FactKind

SADE_SATI = {12: "rising", 1: "peak", 2: "setting"}


def _influenced(planet: str, sign: int, chart: Chart) -> set[int]:
    return {sign} | {(sign + n - 1) % 12 for n in aspect_distances(planet, chart)}


def transit_facts(natal: Chart, when: datetime) -> list[Fact]:
    """Transit facts at `when` (aware datetime). Ids carry the date: transit:<YYYY-MM-DD>:<subject>."""
    now = bodies_at(jd_from_utc(when), natal.config)
    lagna, moon = natal.bodies["Lagna"].sign, natal.bodies["Moon"].sign
    rows = bav(natal)
    sav = [sum(r[i] for r in rows.values()) for i in range(12)]
    day = when.date().isoformat()
    facts = []
    for p in PLANETS:
        b = now[p]
        n, pada, _ = nakshatra(b.lon)
        attrs = {"sign": SIGNS[b.sign], "house_from_lagna": house(b.sign, lagna), "house_from_moon": house(b.sign, moon),
                 "longitude": b.lon, "retro": b.retro, "nakshatra": NAKSHATRAS[n], "pada": pada,
                 "sav_bindus": sav[b.sign]}
        if p in SEVEN:
            attrs["bav_bindus"] = rows[p][b.sign]
        facts.append(Fact(id=f"transit:{day}:{p}", kind=FactKind.transit, varga="transit", subject=p, attrs=attrs))

    h = house(now["Saturn"].sign, moon)
    if h in SADE_SATI:
        facts.append(Fact(id=f"transit:{day}:sade_sati", kind=FactKind.transit, varga="transit", subject="Saturn",
                          object="Moon", attrs={"phase": SADE_SATI[h], "house_from_moon": h}))
    both = _influenced("Jupiter", now["Jupiter"].sign, natal) & _influenced("Saturn", now["Saturn"].sign, natal)
    for sign in sorted(both, key=lambda x: house(x, lagna)):
        facts.append(Fact(id=f"transit:{day}:double_transit:H{house(sign, lagna)}", kind=FactKind.transit,
                          varga="transit", subject="Jupiter+Saturn", object=f"H{house(sign, lagna)}",
                          attrs={"sign": SIGNS[sign], "house_from_moon": house(sign, moon)}))
    return facts


def sign_changes(planet: str, start: datetime, end: datetime, chart: Chart, step_days: float = 5):
    """[(moment, new sign index)] when `planet` changes sign in [start, end), refined to ~1 minute."""
    def sign_at(t):
        return bodies_at(jd_from_utc(t), chart.config)[planet].sign
    out, t, s = [], start, sign_at(start)
    step = timedelta(days=step_days)
    while t < end:
        u = min(t + step, end)
        su = sign_at(u)
        if su != s:  # ponytail: assumes at most one ingress per step; fine for Mars..Saturn and nodes at 5 days
            lo, hi = t, u
            while hi - lo > timedelta(minutes=1):
                mid = lo + (hi - lo) / 2
                lo, hi = (mid, hi) if sign_at(mid) == s else (lo, mid)
            out.append((hi, su))
        t, s = u, su
    return out


def sade_sati_periods(natal: Chart, start: datetime, end: datetime) -> list[tuple[datetime, datetime, str]]:
    """Contiguous (start, end, phase) spans while Saturn is 12th/1st/2nd from the natal Moon."""
    moon = natal.bodies["Moon"].sign
    sat = bodies_at(jd_from_utc(start), natal.config)["Saturn"].sign
    marks = [(start, sat)] + sign_changes("Saturn", start, end, natal) + [(end, None)]
    out = []
    for (t0, s), (t1, _) in zip(marks, marks[1:]):
        phase = SADE_SATI.get(house(s, moon))
        if phase:
            out.append((t0, t1, phase))
    return out
