"""Parashari graha drishti (BPHS ch.26) and same-sign conjunctions, in every varga."""

from itertools import combinations

from jyotish_kit.facts.builders.placements import house, signs
from jyotish_kit.facts.builders.vargas import VARGAS
from jyotish_kit.models import PLANETS, Chart, Fact, FactKind

SPECIAL = {"Mars": (4, 8), "Jupiter": (5, 9), "Saturn": (3, 10)}


def aspect_distances(planet: str, chart: Chart) -> tuple[int, ...]:
    if planet == "Rahu":
        return chart.config.rahu_aspects
    if planet == "Ketu":
        return chart.config.ketu_aspects
    return tuple(sorted((7, *SPECIAL.get(planet, ()))))


def _sep(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def build(chart: Chart) -> list[Fact]:
    facts = []
    for v in VARGAS:
        s = signs(chart, v)
        for p in PLANETS:
            for n in aspect_distances(p, chart):
                target = (s[p] + n - 1) % 12
                h = house(target, s["Lagna"])
                attrs = {"distance": n, "special": n != 7}
                facts.append(Fact(id=f"aspect:{v}:{p}:H{h}", kind=FactKind.aspect, varga=v,
                                  subject=p, object=f"H{h}", attrs=attrs))
                for q in PLANETS:
                    if q != p and s[q] == target:
                        facts.append(Fact(id=f"aspect:{v}:{p}:{q}", kind=FactKind.aspect, varga=v,
                                          subject=p, object=q, attrs=attrs))
        for p, q in combinations(PLANETS, 2):
            if s[p] == s[q] and {p, q} != {"Rahu", "Ketu"}:
                attrs = {"orb": _sep(chart.bodies[p].lon, chart.bodies[q].lon)} if v == "D1" else {}
                facts.append(Fact(id=f"conjunction:{v}:{p}:{q}", kind=FactKind.conjunction, varga=v,
                                  subject=p, object=q, attrs=attrs))
    return facts
