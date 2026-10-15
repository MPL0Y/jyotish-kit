"""Evidence weight = base(classical_strength) x planet strength x stability.

Planet strength applies to favourable evidence only: classical guidance is that yogas formed by weak,
combust or defeated planets give nominal results (BPHS ch.36 closing verses; Phaladeepika ch.6), while an
adverse indication is not made milder by the weakness that constitutes it. Rules tagged neecha_bhanga
are exempt, since their subject is a debilitated planet by definition.
"""

from pydantic import BaseModel

from jyotish_kit.facts.graph import FactGraph
from jyotish_kit.models import PLANETS, Rule


class Weights(BaseModel):
    base: dict[str, float] = {"primary": 1.0, "supporting": 0.6, "minority_view": 0.3}
    dignity: dict[str, float] = {"exalted": 1.25, "moolatrikona": 1.15, "own": 1.1, "great_friend": 1.05,
                                 "friend": 1.0, "neutral": 0.95, "enemy": 0.85, "great_enemy": 0.8,
                                 "debilitated": 0.5}
    navamsa: dict[str, float] = {"exalted": 1.1, "own": 1.05, "debilitated": 0.75}  # yoga bhanga in D9
    baladi: dict[str, float] = {"yuva": 1.0, "kumara": 0.85, "vriddha": 0.8, "bala": 0.75, "mrita": 0.6}
    shadbala_clamp: tuple[float, float] = (0.5, 1.5)
    combust: float = 0.5
    lost_war: float = 0.5
    strength_clamp: tuple[float, float] = (0.2, 1.5)
    # neecha bhanga softens adverse evidence that rests on the same debilitated planet
    neecha_bhanga: float = 0.5
    # favourable evidence resting only on functional malefics (or adverse only on functional benefics)
    functional: float = 0.75
    # draft rules, when explicitly allowed, still count less than verified ones
    draft: float = 1.0


def involved(matched: list[str], facts: FactGraph) -> list[str]:
    """Planets the evidence rests on (absence evidence, prefixed ~, excluded)."""
    out = []
    for fid in matched:
        if fid.startswith("~"):
            continue
        f = facts.get(fid)
        if f is None:
            continue
        for x in (f.subject, f.object if f.kind in ("lordship", "karaka") else None):
            if x in PLANETS and x not in out:
                out.append(x)
    return out


def planet_strength(p: str, facts: FactGraph, w: Weights) -> float:
    lo, hi = w.shadbala_clamp
    sb = facts.get(f"shadbala:D1:{p}")
    s = min(hi, max(lo, sb.attrs["ratio"])) if sb else 1.0
    d1, d9 = facts.get(f"dignity:D1:{p}"), facts.get(f"dignity:D9:{p}")
    s *= w.dignity.get(d1.attrs["status"], 1.0) if d1 else 1.0
    s *= w.navamsa.get(d9.attrs["status"], 1.0) if d9 else 1.0
    av = facts.get(f"avastha:D1:{p}")
    s *= w.baladi.get(av.attrs["baladi"], 1.0) if av else 1.0
    if facts.get(f"combustion:D1:{p}"):
        s *= w.combust
    if any(f.attrs.get("loser") == p for f in facts.query("war")):
        s *= w.lost_war
    return s


def stability(matched: list[str], facts: FactGraph) -> float:
    """Lowest window fraction among the facts the evidence rests on (1 when all hold across the birth window)."""
    fs = [facts.get(i.lstrip("~")) for i in matched]
    return min((f.window_fraction for f in fs if f is not None), default=1.0)


def weigh(rule: Rule, matched: list[str], facts: FactGraph, w: Weights) -> tuple[float, dict[str, float]]:
    """(weight, factors) for a fired rule."""
    factors = {"base": w.base[rule.classical_strength]}
    if rule.effect.polarity > 0 and "neecha_bhanga" not in rule.tags:
        ps = involved(matched, facts)
        if ps:
            lo, hi = w.strength_clamp
            factors["strength"] = min(hi, max(lo, sum(planet_strength(p, facts, w) for p in ps) / len(ps)))
    factors["stability"] = stability(matched, facts)
    if rule.status == "draft":
        factors["draft"] = w.draft
    out = 1.0
    for v in factors.values():
        out *= v
    return out, factors
