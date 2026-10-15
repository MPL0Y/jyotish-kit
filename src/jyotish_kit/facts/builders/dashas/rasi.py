"""Jaimini sign dashas: Chara (K.N. Rao) and Narayana (P.V.R. Narasimha Rao). Lords are sign names.

Shared duration rule: count from the dasha sign to its lord, forward for odd-footed signs
(Ar Ta Ge Li Sc Sg), backward for even-footed ones; minus one; lord in the sign -> 12;
exalted lord +1, debilitated lord -1. Second cycle: 12 - first-cycle years.
Scorpio/Aquarius lord: ChartConfig.co_lords (stronger of Mars/Ketu, Saturn/Rahu by default).

Chara antardashas (K.N. Rao): 12 equal parts, starting from the sign after the dasha sign in the
dasha sign's own direction (odd-footed forward), the dasha sign's own antardasha last.
Narayana: seed = stronger of Lagna and 7th; movable seeds run +-1, fixed +-5, dual by kendras with
trines; even seed reverses, Saturn in seed forces forward, Ketu in seed flips. Antardashas start
from the stronger of the signs holding the dasha sign's lord and the 7th lord, odd forward / even
backward, Saturn there forces forward, Ketu in the dasha sign flips (as JHora).
"""

from jyotish_kit.facts.builders.dashas import facts, split
from jyotish_kit.facts.builders.jaimini import _debilitated, _exalted, rashi_aspects, sign_lord
from jyotish_kit.facts.builders.placements import signs
from jyotish_kit.models import PLANETS, SIGN_LORDS, SIGNS, Chart, DashaPeriod, Fact

ODD_FOOTED = {0, 1, 2, 6, 7, 8}


def years(sign: int, chart: Chart, s: dict[str, int]) -> int:
    lord = sign_lord(sign, chart, s)
    at = s[lord]
    count = ((at - sign) if sign in ODD_FOOTED else (sign - at)) % 12
    y = count or 12
    return y + _exalted(lord, at, chart) - _debilitated(lord, at, chart)


def stronger_sign(a: int, b: int, chart: Chart, s: dict[str, int]) -> int:
    """Jaimini rules: more planets; more of Jupiter/Mercury/lord joining or aspecting; exalted occupant;
    lord in a sign of different oddity; dual > fixed > movable; lord further advanced in its sign."""
    def occupants(x):
        return sum(s[p] == x for p in PLANETS)

    def helpers(x):
        lord = SIGN_LORDS[x]
        return sum(s[h] == x or x in rashi_aspects(s[h]) for h in ("Jupiter", "Mercury", lord))

    def exalted(x):
        return any(s[p] == x and _exalted(p, x, chart) for p in PLANETS)

    def oddity(x):
        return (x % 2) != (s[sign_lord(x, chart, s)] % 2)

    for f in (occupants, helpers, exalted, oddity, lambda x: x % 3):
        fa, fb = f(a), f(b)
        if fa != fb:
            return a if fa > fb else b
    da, db = (chart.bodies[sign_lord(x, chart, s)].deg for x in (a, b))
    return a if da > db else b


def _seq(seed: int, forward: bool) -> list[int]:
    d = 1 if forward else -1
    if seed % 3 == 0:
        return [(seed + d * i) % 12 for i in range(12)]
    if seed % 3 == 1:
        return [(seed + 5 * d * i) % 12 for i in range(12)]
    return [(seed + 3 * d * g + t) % 12 for g in range(4) for t in ((0, 8, 4) if forward else (0, 4, 8))]


def narayana_sequence(seed: int, s: dict[str, int]) -> list[int]:
    if s["Ketu"] == seed:
        return _seq(seed, seed % 2 == 1)
    if s["Saturn"] == seed:
        return [(seed + i) % 12 for i in range(12)]
    return _seq(seed, seed % 2 == 0)


def _run(system: str, chart: Chart, seq: list[int], children, depth: int) -> list[DashaPeriod]:
    s = signs(chart, "D1")
    yd = chart.config.dasha_year_days
    first = {x: years(x, chart, s) for x in seq}
    out, t = [], chart.utc
    for cycle in (first, {x: max(0, 12 - y) for x, y in first.items()}):
        for x in seq:
            ps = split((SIGNS[x],), t, cycle[x], yd, depth, children)
            out += ps
            t = ps[0].end
    return out


def chara(chart: Chart, depth: int = 2) -> list[DashaPeriod]:
    s = signs(chart, "D1")
    lagna = s["Lagna"]
    seq = [(lagna + (i if (lagna + 8) % 12 in ODD_FOOTED else -i)) % 12 for i in range(12)]

    def children(lords, y):
        x = SIGNS.index(lords[-1])
        d = 1 if x in ODD_FOOTED else -1
        return [(SIGNS[(x + d * k) % 12], y / 12) for k in range(1, 13)]
    return _run("chara", chart, seq, children, depth)


def narayana(chart: Chart, depth: int = 2) -> list[DashaPeriod]:
    s = signs(chart, "D1")
    seed = stronger_sign(s["Lagna"], (s["Lagna"] + 6) % 12, chart, s)

    def children(lords, y):
        x = SIGNS.index(lords[-1])
        a = stronger_sign(s[sign_lord(x, chart, s)], s[sign_lord((x + 6) % 12, chart, s)], chart, s)
        fwd = a % 2 == 0 or s["Saturn"] == a
        if s["Ketu"] == x:
            fwd = not fwd
        return [(SIGNS[(a + (k if fwd else -k)) % 12], y / 12) for k in range(12)]
    return _run("narayana", chart, narayana_sequence(seed, s), children, depth)


def build(chart: Chart) -> list[Fact]:
    return facts("chara", chart, chara(chart)) + facts("narayana", chart, narayana(chart))
