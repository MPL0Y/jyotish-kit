"""Tajika varshaphal (annual chart), after Neelakanthi as presented by P.V.R. Narasimha Rao.

- Annual chart: the moment the sidereal Sun returns to its natal longitude in year n, cast for the
  given place (birth place by default; Tajika practice often uses the place of residence).
- Muntha: natal Lagna sign + n.
- Year lord: of the five office-bearers (dina-ratri pati, janma lagna lord, muntha lord, varsha lagna
  lord, tri-rashi pati), the strongest by pancha-vargeeya bala among those aspecting the annual
  Lagna (Tajika: any position but 2/6/8/12); if none aspects, the strongest overall.
- Pancha-vargeeya bala: kshetra 30/15/7.5, uchcha 0..20, hadda 15/7.5/3.75 (Egyptian terms),
  drekkana 10/5/2.5, navamsa 5/2.5/1.25 for own-or-exalted / friend / enemy (natural relations;
  neutral and debilitated score 0, as JHora); total / 4.
- Mudda dasha: Vimshottari compressed into the year; first lord = (janma nakshatra + n - 2) mod 9
  counted from the Sun, balance from the natal Moon's nakshatra fraction.
- Sahams: A - B + C (A and B swapped for night charts where the formula is reversible), +30 deg when C's
  sign is not met walking zodiacally from the sign after B's to A's sign (sign-wise, as JHora).
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from jyotish_kit.ephemeris.engine import bodies_at, compute, jd_from_utc
from jyotish_kit.facts.builders.dashas import split
from jyotish_kit.facts.builders.dashas.vimshottari import YEARS
from jyotish_kit.facts.builders.dignity import EXALTATION, NATURAL, OWN
from jyotish_kit.facts.builders.nakshatra import DASHA_ORDER, nakshatra
from jyotish_kit.facts.builders.placements import house
from jyotish_kit.facts.builders.vargas import varga_sign
from jyotish_kit.models import SEVEN, SIGN_LORDS, SIGNS, BirthData, Chart, DashaPeriod, Fact, FactKind

# Tajika tri-rashi lords per sign: (day, night)
TRI_RASHI = (("Sun", "Jupiter"), ("Venus", "Moon"), ("Saturn", "Mercury"), ("Venus", "Mars"), ("Jupiter", "Sun"),
             ("Moon", "Venus"), ("Mercury", "Saturn"), ("Mars", "Venus"), ("Saturn", "Saturn"), ("Mars", "Mars"),
             ("Jupiter", "Jupiter"), ("Moon", "Moon"))
# Egyptian terms (Ptolemy, Tetrabiblos I.20): (lord, end degree)
HADDA = (
    (("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)),
    (("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)),
    (("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)),
    (("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)),
    (("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)),
    (("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)),
    (("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)),
    (("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)),
    (("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)),
    (("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)),
    (("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)),
    (("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)),
)
# name: (A, B, C, reverse at night). Points: planets, "Lagna", "Punya", "H<n>" (Lagna + 30(n-1)),
# "L<n>" (lord of house n).
SAHAMS = {
    "punya": ("Moon", "Sun", "Lagna", True), "vidya": ("Sun", "Moon", "Lagna", True),
    "yasas": ("Jupiter", "Punya", "Lagna", True), "mitra": ("Jupiter", "Punya", "Venus", True),
    "mahatmya": ("Punya", "Mars", "Lagna", True), "asha": ("Saturn", "Mars", "Lagna", True),
    "bhratri": ("Jupiter", "Saturn", "Lagna", False), "pitri": ("Saturn", "Sun", "Lagna", True),
    "matri": ("Moon", "Venus", "Lagna", True), "putra": ("Jupiter", "Moon", "Lagna", True),
    "jeeva": ("Saturn", "Jupiter", "Lagna", True), "karma": ("Mars", "Mercury", "Lagna", True),
    "roga": ("Lagna", "Moon", "Lagna", False), "kali": ("Jupiter", "Mars", "Lagna", True),
    "bandhu": ("Mercury", "Moon", "Lagna", True), "mrityu": ("H8", "Moon", "Lagna", False),
    "paradesa": ("H9", "L9", "Lagna", False), "artha": ("H2", "L2", "Lagna", False),
    "paradara": ("Venus", "Sun", "Lagna", True), "vanika": ("Moon", "Mercury", "Lagna", True),
    "vivaha": ("Venus", "Saturn", "Lagna", True),
}


def solar_return(natal: Chart, n: int):
    """UTC moment the sidereal Sun returns to its natal longitude, n years after birth."""
    target = natal.bodies["Sun"].lon
    t = natal.utc + timedelta(days=n * natal.config.dasha_year_days)
    for _ in range(6):
        sun = bodies_at(jd_from_utc(t), natal.config)["Sun"]
        diff = (target - sun.lon + 180) % 360 - 180
        t += timedelta(days=diff / sun.speed)
        if abs(diff) < 1e-7:
            break
    return t


def annual_chart(natal: Chart, n: int, lat: float | None = None, lon: float | None = None,
                 tz_name: str | None = None) -> Chart:
    t = solar_return(natal, n)
    tz = tz_name or natal.birth.tz_name
    local = t.astimezone(ZoneInfo(tz))
    birth = BirthData(dt_local=local.replace(tzinfo=None), tz_name=tz, lat=lat if lat is not None else natal.birth.lat,
                      lon=lon if lon is not None else natal.birth.lon, time_uncertainty_min=0, fold=local.fold)
    return compute(birth, natal.config)


def muntha(natal: Chart, n: int) -> int:
    return (natal.bodies["Lagna"].sign + n) % 12


def _relation_points(p: str, sign: int, full: float) -> float:
    lord = SIGN_LORDS[sign]
    if sign in OWN[p] or sign == EXALTATION[p][0] or lord == p:
        return full
    return {1: full / 2, -1: full / 4}.get(NATURAL[p].get(lord, 0), 0.0)


def pancha_vargeeya(chart: Chart) -> dict[str, float]:
    out = {}
    for p in SEVEN:
        b = chart.bodies[p]
        ex = EXALTATION[p][0] * 30 + EXALTATION[p][1]
        d = abs((b.lon - ex + 180) % 360 - 180)  # distance from exaltation point
        uchcha = (180 - d) / 9
        hadda_lord = next(lord for lord, end in HADDA[b.sign] if b.deg < end)
        hadda = 15.0 if hadda_lord == p else {1: 7.5, -1: 3.75}.get(NATURAL[p].get(hadda_lord, 0), 0.0)
        kshetra = 0.0 if b.sign == (EXALTATION[p][0] + 6) % 12 else _relation_points(p, b.sign, 30)
        drek = _relation_points(p, varga_sign(b.lon, "D3"), 10)
        nav = _relation_points(p, varga_sign(b.lon, "D9"), 5)
        out[p] = (kshetra + uchcha + hadda + drek + nav) / 4
    return out


def office_bearers(annual: Chart, natal: Chart, n: int) -> dict[str, str]:
    b, lagna = annual.bodies, annual.bodies["Lagna"].sign
    return {
        "dina_ratri_pati": SIGN_LORDS[b["Sun" if annual.is_day else "Moon"].sign],
        "janma_lagna_lord": SIGN_LORDS[natal.bodies["Lagna"].sign],
        "muntha_lord": SIGN_LORDS[muntha(natal, n)],
        "varsha_lagna_lord": SIGN_LORDS[lagna],
        "tri_rashi_pati": TRI_RASHI[lagna][0 if annual.is_day else 1],
    }


def year_lord(annual: Chart, natal: Chart, n: int) -> str:
    cands = list(dict.fromkeys(office_bearers(annual, natal, n).values()))
    lagna = annual.bodies["Lagna"].sign
    aspecting = [p for p in cands if house(annual.bodies[p].sign, lagna) not in (2, 6, 8, 12)]
    pvb = pancha_vargeeya(annual)
    return max(aspecting or cands, key=lambda p: pvb[p])  # ties: earlier office wins (max is stable)


def mudda(natal: Chart, n: int, depth: int = 2) -> list[DashaPeriod]:
    start, end = solar_return(natal, n), solar_return(natal, n + 1)
    year_days = (end - start) / timedelta(days=1)
    n0, _, frac = nakshatra(natal.bodies["Moon"].lon)
    i = (n0 + n) % 9
    first = DASHA_ORDER[i]
    t = start - timedelta(days=frac * YEARS[first] / 120 * year_days)

    def children(lords, y):
        j = DASHA_ORDER.index(lords[-1])
        return [(DASHA_ORDER[(j + k) % 9], y * YEARS[DASHA_ORDER[(j + k) % 9]] / 120) for k in range(9)]
    out = []
    for k in range(10):  # the 9 lords plus the first again, to cover the whole year
        lord = DASHA_ORDER[(i + k) % 9]
        ps = split((lord,), t, YEARS[lord] / 120, year_days, depth, children)
        out += ps
        t = ps[0].end
    return [p for p in out if p.end > start and p.start < end]


def _between(a: int, b: int, c: int) -> bool:
    """Sign-wise, as JHora: walking from the sign after B up to A's sign, is C's sign met (A's sign counts)?"""
    return 0 < (c - b) % 12 <= ((a - b) % 12 or 12)


def sahams(chart: Chart) -> dict[str, float]:
    b, lagna = chart.bodies, chart.bodies["Lagna"]

    def point(x, done):
        if x == "Punya":
            return done["punya"]
        if x in b:
            return b[x].lon
        if x[0] == "H":
            return (lagna.lon + 30 * (int(x[1:]) - 1)) % 360
        if x[0] == "L":
            return b[SIGN_LORDS[(lagna.sign + int(x[1:]) - 1) % 12]].lon
        return b[x].lon

    out = {}
    for name, (a, bb, c, rev) in SAHAMS.items():
        A, B, C = point(a, out), point(bb, out), point(c, out)
        if rev and not chart.is_day:
            A, B = B, A
        v = A - B + C
        if a != c and not _between(int(A // 30), int(B // 30), int(C // 30)):  # roga: A is C
            v += 30
        out[name] = v % 360
    return out


def facts(natal: Chart, n: int, **place) -> list[Fact]:
    annual = annual_chart(natal, n, **place)
    lagna = annual.bodies["Lagna"].sign
    ns = f"varsha:{n}"
    m = muntha(natal, n)
    out = [
        Fact(id=f"{ns}:chart", kind=FactKind.varshaphal, varga="varsha", subject="annual_chart",
             attrs={"year": n, "start": annual.utc, "lagna": SIGNS[lagna], "is_day": annual.is_day,
                    **{p: SIGNS[annual.bodies[p].sign] for p in (*SEVEN, "Rahu", "Ketu")},
                    **{f"{p}_house": house(annual.bodies[p].sign, lagna) for p in (*SEVEN, "Rahu", "Ketu")}}),
        Fact(id=f"{ns}:muntha", kind=FactKind.varshaphal, varga="varsha", subject="muntha",
             attrs={"sign": SIGNS[m], "house": house(m, lagna), "lord": SIGN_LORDS[m]}),
        Fact(id=f"{ns}:year_lord", kind=FactKind.varshaphal, varga="varsha", subject="year_lord",
             object=year_lord(annual, natal, n), attrs=office_bearers(annual, natal, n)),
    ]
    for name, lon in sahams(annual).items():
        out.append(Fact(id=f"{ns}:saham:{name}", kind=FactKind.varshaphal, varga="varsha", subject=f"saham:{name}",
                        attrs={"longitude": lon, "sign": SIGNS[int(lon // 30)], "house": house(int(lon // 30), lagna)}))
    for p in mudda(natal, n):
        out.append(Fact(id=f"{ns}:mudda:{'/'.join(p.lords)}", kind=FactKind.dasha_period, varga="varsha",
                        subject=p.lords[-1], attrs={"system": "mudda", "level": len(p.lords), "lords": list(p.lords),
                                                    "start": p.start, "end": p.end}))
    return out
