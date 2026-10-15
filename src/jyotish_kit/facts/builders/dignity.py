"""Dignity, panchadha maitri, combustion and graha yuddha. Tables per BPHS ch.3."""

from itertools import combinations

from jyotish_kit.facts.builders.aspects import _sep
from jyotish_kit.facts.builders.placements import signs
from jyotish_kit.facts.builders.vargas import VARGAS
from jyotish_kit.models import SEVEN, SIGN_LORDS, SIGNS, Chart, Fact, FactKind

# (sign index, deep exaltation degree within sign)
EXALTATION = {"Sun": (0, 10), "Moon": (1, 3), "Mars": (9, 28), "Mercury": (5, 15),
              "Jupiter": (3, 5), "Venus": (11, 27), "Saturn": (6, 20)}
OWN = {"Sun": {4}, "Moon": {3}, "Mars": {0, 7}, "Mercury": {2, 5},
       "Jupiter": {8, 11}, "Venus": {1, 6}, "Saturn": {9, 10}}
# Natural friendship: +1 friend, 0 neutral, -1 enemy (BPHS ch.3). Nodes excluded: no consensus.
_F, _N, _E = 1, 0, -1
NATURAL = {
    "Sun": {"Moon": _F, "Mars": _F, "Jupiter": _F, "Mercury": _N, "Venus": _E, "Saturn": _E},
    "Moon": {"Sun": _F, "Mercury": _F, "Mars": _N, "Jupiter": _N, "Venus": _N, "Saturn": _N},
    "Mars": {"Sun": _F, "Moon": _F, "Jupiter": _F, "Venus": _N, "Saturn": _N, "Mercury": _E},
    "Mercury": {"Sun": _F, "Venus": _F, "Mars": _N, "Jupiter": _N, "Saturn": _N, "Moon": _E},
    "Jupiter": {"Sun": _F, "Moon": _F, "Mars": _F, "Saturn": _N, "Mercury": _E, "Venus": _E},
    "Venus": {"Mercury": _F, "Saturn": _F, "Mars": _N, "Jupiter": _N, "Sun": _E, "Moon": _E},
    "Saturn": {"Mercury": _F, "Venus": _F, "Jupiter": _N, "Sun": _E, "Moon": _E, "Mars": _E},
}
COMPOUND = {2: "great_friend", 1: "friend", 0: "neutral", -1: "enemy", -2: "great_enemy"}
WAR_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")


def relationships(chart: Chart) -> dict[tuple[str, str], tuple[int, int, int]]:
    """(p, q) -> (natural, temporal, compound score) of p's view of q. Temporal uses D1 (BPHS ch.3)."""
    s = signs(chart, "D1")
    out = {}
    for p in SEVEN:
        for q in SEVEN:
            if p != q:
                temporal = 1 if (s[q] - s[p]) % 12 + 1 in (2, 3, 4, 10, 11, 12) else -1
                nat = NATURAL[p][q]
                out[p, q] = (nat, temporal, nat + temporal)
    return out


def _status(p: str, sign: int, deg: float | None, chart: Chart, rel) -> str:
    """deg=None for vargas: sign-only dignity, moolatrikona sign counts as own."""
    cfg = chart.config
    ex = EXALTATION[p][0] if p in EXALTATION else cfg.node_exaltation.get(p)
    mt = cfg.moolatrikona.get(p)
    if mt and sign == mt[0] and deg is not None:
        # Moon/Mercury share exaltation and MT sign: exalted below the MT range, own above it.
        if mt[1] <= deg < mt[2]:
            return "moolatrikona"
        return "exalted" if sign == ex and deg < mt[1] else "own"
    if sign == ex:
        return "exalted"
    if ex is not None and sign == (ex + 6) % 12:
        return "debilitated"
    if sign in OWN.get(p, ()) or (mt and sign == mt[0]):
        return "own"
    if p not in SEVEN:
        return "none"
    return COMPOUND[rel[p, SIGN_LORDS[sign]][2]]


def build(chart: Chart) -> list[Fact]:
    cfg, b = chart.config, chart.bodies
    rel = relationships(chart)
    facts = []
    dignified = [*SEVEN, *(n for n in ("Rahu", "Ketu") if n in cfg.node_exaltation)]
    for v in VARGAS:
        s = signs(chart, v)
        for p in dignified:
            attrs = {"status": _status(p, s[p], b[p].deg if v == "D1" else None, chart, rel)}
            if v == "D1" and p in EXALTATION:
                sign, d = EXALTATION[p]
                attrs["from_deep_exaltation"] = _sep(b[p].lon, sign * 30 + d)
            facts.append(Fact(id=f"dignity:{v}:{p}", kind=FactKind.dignity, varga=v, subject=p, attrs=attrs))

    for (p, q), (nat, tmp, comp) in rel.items():
        facts.append(Fact(id=f"relationship:D1:{p}:{q}", kind=FactKind.relationship, subject=p, object=q,
                          attrs={"natural": nat, "temporal": tmp, "compound": COMPOUND[comp]}))

    for p, orb in cfg.combustion_orbs.items():
        if b[p].retro and p in cfg.combustion_orbs_retro:
            orb = cfg.combustion_orbs_retro[p]
        dist = _sep(b[p].lon, b["Sun"].lon)
        if dist <= orb:
            facts.append(Fact(id=f"combustion:D1:{p}", kind=FactKind.combustion, subject=p, object="Sun",
                              attrs={"distance": dist, "orb": float(orb)}))

    for p, q in combinations(WAR_PLANETS, 2):
        sep = _sep(b[p].lon, b[q].lon)
        if sep <= cfg.war_orb:
            if cfg.war_winner == "north_latitude":
                win = p if b[p].lat > b[q].lat else q
            else:
                win = p if b[p].magnitude < b[q].magnitude else q
            facts.append(Fact(id=f"war:D1:{p}:{q}", kind=FactKind.war, subject=p, object=q,
                              attrs={"separation": sep, "winner": win, "loser": q if win == p else p,
                                     "rule": cfg.war_winner}))
    return facts
