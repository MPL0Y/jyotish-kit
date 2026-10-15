"""Krishnamurti Paddhati: star/sub/sub-sub lords, 4-level significators, ruling planets.

Positions and Placidus cusps are re-expressed in ChartConfig.kp_ayanamsa.
Significator levels (K.S. Krishnamurti, KP Reader I-IV), strongest first:
  1 houses occupied by the planet's star lord, 2 houses occupied by the planet,
  3 houses owned by the star lord, 4 houses owned by the planet.
Rahu/Ketu additionally signify the houses of their sign lord (occupied and owned).
"""

from jyotish_kit.facts.builders.dashas.vimshottari import YEARS
from jyotish_kit.facts.builders.nakshatra import DASHA_ORDER, SPAN
from jyotish_kit.models import PLANETS, SIGN_LORDS, Chart, Fact, FactKind

DAY_LORDS = ("Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun")  # Monday=0 (datetime.weekday)


def lords(lon: float, depth: int = 3) -> list[str]:
    """[sign lord, star lord, sub lord, sub-sub lord, ...] for a longitude (depth counts below star)."""
    lon %= 360
    n = int(lon // SPAN)
    star = DASHA_ORDER[n % 9]
    out = [SIGN_LORDS[int(lon // 30)], star]
    offset, length, start = lon - n * SPAN, SPAN, star
    for _ in range(depth - 1):
        i = DASHA_ORDER.index(start)
        for k in range(9):
            lord = DASHA_ORDER[(i + k) % 9]
            seg = length * YEARS[lord] / 120
            if offset < seg or k == 8:
                break
            offset -= seg
        out.append(lord)
        length, start = seg, lord
    return out


def kp_positions(chart: Chart) -> tuple[dict[str, float], list[float]]:
    shift = chart.ayanamsa - chart.ayanamsa_kp
    bodies = {n: (b.lon + shift) % 360 for n, b in chart.bodies.items()}
    return bodies, [(c + shift) % 360 for c in chart.placidus_cusps]


def bhava_of(lon: float, cusps: list[float]) -> int:
    """KP house 1..12: from cusp i up to cusp i+1."""
    for i in range(12):
        if (lon - cusps[i]) % 360 < (cusps[(i + 1) % 12] - cusps[i]) % 360:
            return i + 1
    raise AssertionError("unreachable")


def significators(chart: Chart) -> dict[str, dict[int, list[int]]]:
    bodies, cusps = kp_positions(chart)
    occ = {p: bhava_of(bodies[p], cusps) for p in PLANETS}
    owned = {p: sorted(h for h in range(1, 13) if SIGN_LORDS[int(cusps[h - 1] // 30)] == p) for p in PLANETS}
    out = {}
    for p in PLANETS:
        star = lords(bodies[p], 1)[1]
        lv = {1: [occ[star]], 2: [occ[p]], 3: owned[star], 4: owned[p]}
        if p in ("Rahu", "Ketu"):
            sl = SIGN_LORDS[int(bodies[p] // 30)]
            lv[4] = sorted(set(lv[4]) | {occ[sl], *owned[sl]})
        out[p] = lv
    return out


def ruling_planets(chart: Chart) -> dict[str, str]:
    """Ruling planets at the chart's own moment (use a chart cast for 'now' for horary/timing)."""
    bodies, _ = kp_positions(chart)
    from zoneinfo import ZoneInfo
    vedic_day = chart.sunrise.astimezone(ZoneInfo(chart.birth.tz_name)).weekday()
    m, lg = lords(bodies["Moon"], 2), lords(bodies["Lagna"], 2)
    return {"day_lord": DAY_LORDS[vedic_day], "moon_sign_lord": m[0], "moon_star_lord": m[1],
            "moon_sub_lord": m[2], "lagna_sign_lord": lg[0], "lagna_star_lord": lg[1], "lagna_sub_lord": lg[2]}


def build(chart: Chart) -> list[Fact]:
    bodies, cusps = kp_positions(chart)
    facts = []
    for name, lon in [*bodies.items(), *((f"C{i + 1}", c) for i, c in enumerate(cusps))]:
        sign_l, star, sub, subsub = lords(lon, 3)
        attrs = {"sign_lord": sign_l, "star_lord": star, "sub_lord": sub, "sub_sub_lord": subsub, "longitude": lon}
        if not name.startswith("C"):
            attrs["house"] = bhava_of(lon, cusps)
        facts.append(Fact(id=f"kp_lords:KP:{name}", kind=FactKind.kp_lords, varga="KP", subject=name, attrs=attrs))
    for p, lv in significators(chart).items():
        facts.append(Fact(id=f"kp_significator:KP:{p}", kind=FactKind.kp_significator, varga="KP", subject=p,
                          attrs={f"level{k}": v for k, v in lv.items()}
                          | {"houses": sorted({h for v in lv.values() for h in v})}))
    return facts
