from jyotish_kit.facts.builders.nakshatra import NAKSHATRAS, nakshatra, nakshatra_lord
from jyotish_kit.facts.builders.vargas import VARGAS, varga_sign
from jyotish_kit.models import SIGNS, Chart, Fact, FactKind


def signs(chart: Chart, varga: str) -> dict[str, int]:
    """Sign index of every body (incl. Lagna) in a varga."""
    return {n: varga_sign(b.lon, varga) for n, b in chart.bodies.items()}


def house(sign: int, lagna_sign: int) -> int:
    """Whole-sign house (1..12) of a sign counted from the lagna sign."""
    return (sign - lagna_sign) % 12 + 1


def build(chart: Chart) -> list[Fact]:
    facts = []
    for v in VARGAS:
        s = signs(chart, v)
        for name, b in chart.bodies.items():
            attrs = {"sign": SIGNS[s[name]], "house": house(s[name], s["Lagna"])}
            if v == "D1":
                n, pada, _ = nakshatra(b.lon)
                attrs |= {"longitude": b.lon, "degree": b.deg, "speed": b.speed, "retro": b.retro,
                          "nakshatra": NAKSHATRAS[n], "pada": pada, "nakshatra_lord": nakshatra_lord(n)}
            facts.append(Fact(id=f"placement:{v}:{name}", kind=FactKind.placement, varga=v,
                              subject=name, attrs=attrs))
    return facts
