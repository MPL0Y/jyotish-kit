"""Jaimini facts: chara karakas, rashi drishti, arudha padas, upapada, karakamsha, special lagnas.

Sources: BPHS ch.29 (arudha), ch.32 (chara karakas), Jaimini Upadesa Sutras 1.1 (rashi drishti).
Co-lord strength for Scorpio/Aquarius follows the rule chain in P.V.R. Narasimha Rao,
"Vedic Astrology: An Integrated Approach" (as also implemented by JHora).
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from jyotish_kit.facts.builders.dignity import EXALTATION
from jyotish_kit.facts.builders.nakshatra import nakshatra
from jyotish_kit.facts.builders.placements import house, signs
from jyotish_kit.facts.builders.vargas import varga_sign
from jyotish_kit.models import PLANETS, SEVEN, SIGN_LORDS, SIGNS, Chart, Fact, FactKind

KARAKAS = {8: ("AK", "AmK", "BK", "MK", "PiK", "PK", "GK", "DK"),
           7: ("AK", "AmK", "BK", "MK", "PK", "GK", "DK")}
CO_LORD = {7: "Ketu", 10: "Rahu"}  # Scorpio -> Mars/Ketu, Aquarius -> Saturn/Rahu


def rashi_aspects(sign: int) -> set[int]:
    """Signs aspected by a sign. Movable aspect fixed and fixed aspect movable, except the adjacent
    one; dual signs aspect the other duals."""
    kind = sign % 3  # 0 movable, 1 fixed, 2 dual
    if kind == 2:
        return {s for s in range(2, 12, 3) if s != sign}
    if kind == 0:
        return {s for s in range(1, 12, 3) if s != (sign + 1) % 12}
    return {s for s in range(0, 12, 3) if s != (sign - 1) % 12}


def chara_karakas(chart: Chart) -> dict[str, str]:
    n = chart.config.chara_karakas
    b = chart.bodies
    cands = list(SEVEN) + (["Rahu"] if n == 8 else [])
    deg = {p: (30 - b[p].deg) if p == "Rahu" else b[p].deg for p in cands}
    return dict(zip(KARAKAS[n], sorted(cands, key=deg.get, reverse=True)))


def _exalted(p: str, sign: int, chart: Chart) -> bool:
    if p in EXALTATION:
        return sign == EXALTATION[p][0]
    return sign in chart.config.jaimini_node_exaltation.get(p, ())


def _debilitated(p: str, sign: int, chart: Chart) -> bool:
    return _exalted(p, (sign + 6) % 12, chart)


def stronger(p: str, q: str, chart: Chart, s: dict[str, int]) -> str:
    """Stronger of a sign's two co-lords (p = Mars/Saturn, q = Ketu/Rahu)."""
    own = next(k for k, v in CO_LORD.items() if v == q)
    if (s[p] == own) != (s[q] == own):  # one sits in the co-owned sign: the other one rules it
        return q if s[p] == own else p

    def conj(x):
        return sum(s[o] == s[x] for o in PLANETS if o != x)

    def helpers(x):  # Jupiter, Mercury, dispositor conjoining or rashi-aspecting
        aspected_by = {o for o in PLANETS if s[x] in rashi_aspects(s[o]) or s[o] == s[x]}
        return sum(h in aspected_by for h in ("Jupiter", "Mercury", SIGN_LORDS[s[x]]))

    checks = (conj, helpers, lambda x: _exalted(x, s[x], chart), lambda x: s[x] % 3,  # dual > fixed > movable
              lambda x: chart.bodies[x].deg)
    for f in checks:
        a, c = f(p), f(q)
        if a != c:
            return p if a > c else q
    return p


def sign_lord(sign: int, chart: Chart, s: dict[str, int]) -> str:
    lord = SIGN_LORDS[sign]
    if sign in CO_LORD and chart.config.co_lords == "stronger":
        return stronger(lord, CO_LORD[sign], chart, s)
    return lord


def arudhas(chart: Chart, s: dict[str, int]) -> dict[int, int]:
    """house -> arudha sign (BPHS 29.1-3, with the 1st/7th -> 10th exception)."""
    out = {}
    for h in range(1, 13):
        sign = (s["Lagna"] + h - 1) % 12
        lord_sign = s[sign_lord(sign, chart, s)]
        a = (lord_sign + (lord_sign - sign)) % 12
        if (a - sign) % 12 in (0, 6):
            a = (a + 9) % 12
        out[h] = a
    return out


def special_lagnas(chart: Chart) -> dict[str, float]:
    """Bhava, Hora, Ghati lagnas: Sun at sunrise + ishta kala at 1 sign per 5, 2.5, 1 ghati."""
    sunrise, sun = chart.sunrise, chart.sun_lon_at_sunrise
    if chart.config.special_lagna_sunrise == "civil_date":
        tz = ZoneInfo(chart.birth.tz_name)
        if chart.next_sunrise.astimezone(tz).date() == chart.utc.astimezone(tz).date():
            sunrise, sun = chart.next_sunrise, chart.sun_lon_at_next_sunrise
    minutes = (chart.utc - sunrise) / timedelta(minutes=1)
    out = {name: (sun + minutes * rate) % 360 for name, rate in (("BL", 0.25), ("HL", 0.5), ("GL", 1.25))}
    _, _, frac = nakshatra(chart.bodies["Moon"].lon)
    out["SL"] = (chart.bodies["Lagna"].lon + frac * 360) % 360  # Sree lagna
    return out


def varnada(lagna: int, hl: int) -> int:
    """Varnada lagna sign (B.V. Raman's counting). Odd signs count from Aries, even from Pisces backwards."""
    def count(x):
        return x + 1 if x % 2 == 0 else 12 - x
    c1, c2 = count(lagna), count(hl)
    c = (c1 + c2) % 12 if (lagna % 2) == (hl % 2) else abs(c1 - c2) % 12
    return (c - 1) % 12 if lagna % 2 == 0 else (12 - c) % 12


def build(chart: Chart) -> list[Fact]:
    s = signs(chart, "D1")
    lagna = s["Lagna"]
    facts = []
    ks = chara_karakas(chart)
    for k, p in ks.items():
        facts.append(Fact(id=f"karaka:D1:{k}", kind=FactKind.karaka, subject=k, object=p,
                          attrs={"scheme": chart.config.chara_karakas}))
    kk = varga_sign(chart.bodies[ks["AK"]].lon, "D9")
    facts.append(Fact(id="special_lagna:D1:Karakamsha", kind=FactKind.special_lagna, subject="Karakamsha",
                      attrs={"sign": SIGNS[kk], "house": house(kk, lagna)}))

    for h, a in arudhas(chart, s).items():
        names = [f"A{h}"] + (["UL"] if h == 12 else []) + (["AL"] if h == 1 else [])
        for n in names:
            facts.append(Fact(id=f"arudha:D1:{n}", kind=FactKind.arudha, subject=n,
                              attrs={"sign": SIGNS[a], "house": house(a, lagna)}))

    spl = special_lagnas(chart)
    for name, lon in spl.items():
        sg = int(lon // 30)
        facts.append(Fact(id=f"special_lagna:D1:{name}", kind=FactKind.special_lagna, subject=name,
                          attrs={"sign": SIGNS[sg], "house": house(sg, lagna), "longitude": lon}))
    vl = varnada(lagna, int(spl["HL"] // 30))
    facts.append(Fact(id="special_lagna:D1:VL", kind=FactKind.special_lagna, subject="VL",
                      attrs={"sign": SIGNS[vl], "house": house(vl, lagna), "method": "raman"}))

    for p in PLANETS:
        for t in sorted(rashi_aspects(s[p])):
            facts.append(Fact(id=f"rashi_aspect:D1:{p}:H{house(t, lagna)}", kind=FactKind.rashi_aspect,
                              subject=p, object=f"H{house(t, lagna)}", attrs={"sign": SIGNS[t]}))
            for q in PLANETS:
                if q != p and s[q] == t:
                    facts.append(Fact(id=f"rashi_aspect:D1:{p}:{q}", kind=FactKind.rashi_aspect,
                                      subject=p, object=q))
    return facts
