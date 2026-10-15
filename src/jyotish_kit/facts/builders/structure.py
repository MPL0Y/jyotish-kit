"""Structural facts a reading starts from: functional nature by Lagna, sign exchanges, argala,
sensitive degrees and bhava chalit.

Functional nature (BPHS ch.34, general rules 34.2-12): trikona lords auspicious; lords of 3/6/11
malefic; natural benefics owning kendras lose beneficence (kendradhipati dosha) and natural malefics
owning kendras lose maleficence; 2nd/12th lords neutral, acting by association; the 8th lord inauspicious
unless it also rules the Lagna (Sun and Moon exempt); a planet owning a kendra (4/7/10) and a trikona
(5/9) is yogakaraka; the Lagna lord is auspicious. Net nature, in this order: Lagna lord -> benefic;
yogakaraka; trikona lord -> benefic, or mixed if it also owns 3/6/8/11; owns 3/6/8/11 -> malefic;
otherwise neutral. Marakas: lords of 2 and 7. Badhaka: lord of the 11th (movable Lagna), 9th (fixed)
or 7th (dual).

Parivartana (Phaladeepika 6.32-34): maha between good houses, khala involving the 3rd, dainya
involving 6/8/12.

Argala (BPHS ch.31): planets in the 2nd, 4th, 11th (primary) and 5th (secondary) from a house; obstructed
by planets in the 12th, 10th, 3rd and 9th respectively. Malefics in the 3rd also give argala
(vipareeta). Effective when the argala planets outnumber the obstructing ones.

Sensitive degrees:
- vargottama: same sign in D1 and D9.
- gandanta: last pada of Ashlesha/Jyeshtha/Revati or first pada of Magha/Mula/Ashwini (the
  water-to-fire junctions).
- rashi sandhi: within 1 deg of a sign boundary.
- pushkara navamsa: the two benefic navamsas of each sign (fire: 7th and 9th; earth: 3rd and 5th;
  air: 6th and 8th; water: 1st and 3rd).
- pushkara bhaga: the degree of each sign per ChartConfig.pushkara_bhaga (in [n-1, n), as JHora).
- mrityu bhaga: the table carried by JHora/PyJHora (classical source not yet pinned), within its
  per-column tolerance.

Bhava chalit: Sripati bhavas, madhyas from the trisected quadrants, sandhis midway between madhyas.
"""

from jyotish_kit.facts.builders.nakshatra import nakshatra
from jyotish_kit.facts.builders.placements import house, signs
from jyotish_kit.facts.builders.shadbala import bhava_madhya
from jyotish_kit.facts.builders.vargas import varga_sign
from jyotish_kit.models import PLANETS, SEVEN, SIGN_LORDS, SIGNS, Chart, Fact, FactKind

NATURAL_BENEFICS = {"Moon", "Mercury", "Jupiter", "Venus"}
NATURAL_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
BADHAKA_HOUSE = (11, 9, 7)  # movable, fixed, dual Lagna
PUSHKARA_NAVAMSA = ((6, 8), (2, 4), (5, 7), (0, 2))  # 0-based navamsa numbers by element: fire earth air water
PUSHKARA_BHAGA = {
    "jataka_parijata": (21, 14, 18, 8, 19, 9, 24, 11, 23, 14, 19, 9),
    "element": (21, 14, 24, 7) * 3,
}
# Mrityu bhaga: [sign][Sun..Ketu, Mandi, Lagna] degree, and tolerance per column (JHora table).
MRITYU_BHAGA = ((20, 26, 19, 15, 19, 28, 10, 14, 8, 23, 1), (9, 12, 28, 14, 29, 15, 4, 13, 18, 24, 9),
                (12, 13, 25, 13, 12, 11, 7, 12, 20, 11, 22), (6, 25, 23, 12, 27, 17, 9, 11, 10, 12, 22),
                (8, 24, 29, 8, 6, 10, 12, 24, 21, 13, 25), (24, 11, 28, 18, 4, 13, 16, 23, 22, 14, 2),
                (16, 26, 14, 20, 13, 4, 3, 22, 23, 8, 4), (17, 14, 21, 10, 10, 6, 18, 21, 24, 18, 23),
                (22, 13, 2, 21, 17, 27, 28, 10, 11, 20, 18), (2, 25, 15, 22, 11, 12, 14, 20, 12, 10, 20),
                (3, 5, 11, 7, 15, 29, 13, 18, 13, 21, 24), (23, 12, 6, 5, 28, 19, 15, 8, 14, 22, 10))
MRITYU_TOLERANCE = (1 / 3, 2 / 3, 0.25, 2 / 3, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 2 / 3)
MRITYU_COLUMN = {**{p: i for i, p in enumerate(PLANETS)}, "Mandi": 9, "Lagna": 10}


INDU_KALAS = {"Sun": 30, "Moon": 16, "Mars": 6, "Mercury": 8, "Jupiter": 10, "Venus": 12, "Saturn": 1}


def indu_lagna(s: dict[str, int]) -> int:
    """Sign of Indu Lagna (B.V. Raman; JHora): kalas of the 9th lords from Lagna and Moon, mod 12,
    counted from the Moon."""
    n = (INDU_KALAS[SIGN_LORDS[(s["Lagna"] + 8) % 12]] + INDU_KALAS[SIGN_LORDS[(s["Moon"] + 8) % 12]]) % 12 or 12
    return (s["Moon"] + n - 1) % 12


def bhrigu_bindu(chart: Chart) -> float:
    """Midpoint of the arc from Rahu forward to the Moon."""
    r, m = chart.bodies["Rahu"].lon, chart.bodies["Moon"].lon
    return (r + ((m - r) % 360) / 2) % 360


def owned_houses(p: str, lagna: int) -> list[int]:
    return sorted(house(s, lagna) for s in range(12) if SIGN_LORDS[s] == p)


def functional_nature(p: str, lagna: int) -> dict:
    hs = set(owned_houses(p, lagna))
    bad = hs & {3, 6, 11} | ({8} & hs if p not in ("Sun", "Moon") else set())
    kendra, trikona = hs & {4, 7, 10}, hs & {5, 9}
    yogakaraka = bool(kendra and trikona)
    if 1 in hs:
        nature = "benefic"
    elif yogakaraka:
        nature = "yogakaraka"
    elif trikona:
        nature = "mixed" if bad else "benefic"
    elif bad:
        nature = "malefic"
    else:
        nature = "neutral"
    return {"houses_owned": sorted(hs), "nature": nature, "yogakaraka": yogakaraka,
            "kendradhipati_dosha": bool(kendra) and not trikona and 1 not in hs and p in NATURAL_BENEFICS,
            "maraka": bool(hs & {2, 7}), "badhaka": BADHAKA_HOUSE[lagna % 3] in hs,
            "dusthana_lord": sorted(hs & {6, 8, 12}), "natural": "benefic" if p in NATURAL_BENEFICS else "malefic"}


def exchanges(s: dict[str, int]) -> list[tuple[str, str, int, int]]:
    out = []
    for i, p in enumerate(SEVEN):
        for q in SEVEN[i + 1:]:
            if SIGN_LORDS[s[p]] == q and SIGN_LORDS[s[q]] == p:
                out.append((p, q, house(s[p], s["Lagna"]), house(s[q], s["Lagna"])))
    return out


def argala(s: dict[str, int], ref: int) -> dict:
    def at(n):
        return [p for p in PLANETS if s[p] == (ref + n - 1) % 12]
    out = {}
    for src, block in ((2, 12), (4, 10), (11, 3), (5, 9)):
        a, v = at(src), at(block)
        out[src] = {"argala": a, "virodha": v, "effective": len(a) > len(v)}
    vip = [p for p in at(3) if p in NATURAL_MALEFICS]
    out[3] = {"argala": vip, "virodha": at(11), "effective": len(vip) > len(at(11)), "vipareeta": True}
    return out


def sensitive(name: str, lon: float, cfg) -> dict:
    sign, deg = int(lon // 30), lon % 30
    n, pada, _ = nakshatra(lon)
    elem = sign % 4
    nav = int(deg // (10 / 3))
    out = {"vargottama": varga_sign(lon, "D9") == sign,
           "gandanta": (n in (8, 17, 26) and pada == 4) or (n in (9, 18, 0) and pada == 1),
           "rashi_sandhi": deg < 1 or deg > 29, "boundary_margin": min(deg, 30 - deg),
           "pushkara_navamsa": nav in PUSHKARA_NAVAMSA[elem]}
    pb = PUSHKARA_BHAGA[cfg.pushkara_bhaga][sign]
    out["pushkara_bhaga"] = pb - 1 <= deg < pb
    col = MRITYU_COLUMN.get(name)
    if col is not None:
        out["mrityu_bhaga"] = abs(deg - MRITYU_BHAGA[sign][col]) <= MRITYU_TOLERANCE[col]
    return out


def chalit(chart: Chart) -> dict[str, int]:
    """Bhava (1..12) of each body by Sripati bhava sandhis."""
    mad = bhava_madhya(chart)
    sandhi = [(mad[i - 1] + ((mad[i] - mad[i - 1]) % 360) / 2) % 360 for i in range(12)]  # start of bhava i+1
    out = {}
    for name, b in chart.bodies.items():
        out[name] = next(i + 1 for i in range(12)
                         if (b.lon - sandhi[i]) % 360 < (sandhi[(i + 1) % 12] - sandhi[i]) % 360)
    return out


def build(chart: Chart) -> list[Fact]:
    from jyotish_kit.facts.builders.panchanga import upagrahas  # avoid import cycle at module load
    facts = []
    s = signs(chart, "D1")
    lagna = s["Lagna"]
    for p in SEVEN:
        facts.append(Fact(id=f"functional:D1:{p}", kind=FactKind.functional, subject=p,
                          attrs=functional_nature(p, lagna)))
    for node in ("Rahu", "Ketu"):
        disp = SIGN_LORDS[s[node]]
        facts.append(Fact(id=f"functional:D1:{node}", kind=FactKind.functional, subject=node, object=disp,
                          attrs={"nature": "as_dispositor", "dispositor": disp,
                                 "dispositor_nature": functional_nature(disp, lagna)["nature"]}))
    for v in ("D1", "D9"):
        sv = signs(chart, v)
        for p, q, hp, hq in exchanges(sv):
            kind = "dainya" if {hp, hq} & {6, 8, 12} else "khala" if 3 in (hp, hq) else "maha"
            facts.append(Fact(id=f"exchange:{v}:{p}:{q}", kind=FactKind.exchange, varga=v, subject=p, object=q,
                              attrs={"houses": [hp, hq], "type": kind}))
    for h in range(1, 13):
        facts.append(Fact(id=f"argala:D1:H{h}", kind=FactKind.argala, subject=f"H{h}",
                          attrs={str(k): v for k, v in argala(s, (lagna + h - 1) % 12).items()}))
    il, bb = indu_lagna(s), bhrigu_bindu(chart)
    facts.append(Fact(id="special_lagna:D1:IL", kind=FactKind.special_lagna, subject="IL",
                      attrs={"sign": SIGNS[il], "house": house(il, lagna)}))
    facts.append(Fact(id="special_lagna:D1:BB", kind=FactKind.special_lagna, subject="BB",
                      attrs={"longitude": bb, "sign": SIGNS[int(bb // 30)], "house": house(int(bb // 30), lagna)}))
    ch = chalit(chart)
    points = {n: b.lon for n, b in chart.bodies.items()} | {"Mandi": upagrahas(chart)["Mandi"]}
    for name, lon in points.items():
        attrs = sensitive(name, lon, chart.config)
        if name in ch:
            attrs["chalit_bhava"] = ch[name]
            attrs["rashi_house"] = house(int(lon // 30), lagna)
        facts.append(Fact(id=f"sensitive:D1:{name}", kind=FactKind.sensitive, subject=name, attrs=attrs))
    return facts

