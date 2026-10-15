"""Planetary avasthas (BPHS ch.45): baladi (age), jagradadi (wakefulness), deeptadi (mood).

Deeptadi mapping (Santhanam's BPHS): exalted deepta, own/moolatrikona swastha, great friend pramudita,
friend shanta, neutral deena, enemy duhkhita, great enemy khala; debilitated is taken as khala.
Overlays reported separately: kopa (combust) and vikala (sharing a sign with a natural malefic).
"""

from jyotish_kit.facts.builders.dignity import _status, relationships
from jyotish_kit.facts.builders.placements import signs
from jyotish_kit.models import SEVEN, Chart, Fact, FactKind

BALADI = ("bala", "kumara", "yuva", "vriddha", "mrita")
DEEPTADI = {"exalted": "deepta", "moolatrikona": "swastha", "own": "swastha", "great_friend": "pramudita",
            "friend": "shanta", "neutral": "deena", "enemy": "duhkhita", "great_enemy": "khala",
            "debilitated": "khala"}
JAGRADADI = {"exalted": "jagrat", "moolatrikona": "jagrat", "own": "jagrat", "great_friend": "swapna",
             "friend": "swapna", "neutral": "swapna", "enemy": "sushupti", "great_enemy": "sushupti",
             "debilitated": "sushupti"}
MALEFICS = ("Sun", "Mars", "Saturn", "Rahu", "Ketu")


def build(chart: Chart) -> list[Fact]:
    from jyotish_kit.facts.builders.aspects import _sep
    b, rel, s = chart.bodies, relationships(chart), signs(chart, "D1")
    facts = []
    for p in SEVEN:
        part = int(b[p].deg // 6)
        baladi = BALADI[part if b[p].sign % 2 == 0 else 4 - part]  # even signs run backwards
        status = _status(p, b[p].sign, b[p].deg, chart, rel)
        orb = chart.config.combustion_orbs_retro.get(p) if b[p].retro else None
        orb = orb or chart.config.combustion_orbs.get(p)
        facts.append(Fact(id=f"avastha:D1:{p}", kind=FactKind.avastha, subject=p, attrs={
            "baladi": baladi, "jagradadi": JAGRADADI[status], "deeptadi": DEEPTADI[status],
            "kopa": bool(orb and _sep(b[p].lon, b["Sun"].lon) <= orb),
            "vikala": any(m != p and s[m] == s[p] for m in MALEFICS)}))
    return facts
