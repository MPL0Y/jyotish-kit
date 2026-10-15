from jyotish_kit.facts.builders.placements import house, signs
from jyotish_kit.facts.builders.vargas import VARGAS
from jyotish_kit.models import SIGN_LORDS, SIGNS, Chart, Fact, FactKind


def build(chart: Chart) -> list[Fact]:
    facts = []
    for v in VARGAS:
        s = signs(chart, v)
        for h in range(1, 13):
            sign = (s["Lagna"] + h - 1) % 12
            lord = SIGN_LORDS[sign]
            facts.append(Fact(
                id=f"lordship:{v}:H{h}", kind=FactKind.lordship, varga=v, subject=f"H{h}", object=lord,
                attrs={"sign": SIGNS[sign], "lord_house": house(s[lord], s["Lagna"])}))
    return facts
