"""Kalachakra dasha (BPHS ch.46), P.V.R. Narasimha Rao's table method. Lords are sign names.

The Moon's nakshatra pada selects a 9-sign cycle (savya/apasavya groups) whose sign years sum to its
paramayush; the elapsed fraction of the pada locates the running sign at birth. Later dashas continue
through the following padas' cycles. Antardashas: the cycle rotated to start at the dasha sign,
proportional to sign years. Gati jumps (manduka/simhavalokana) carry no special handling.
"""

from datetime import timedelta

from jyotish_kit.facts.builders.dashas import facts, split
from jyotish_kit.facts.builders.nakshatra import nakshatra
from jyotish_kit.models import SIGNS, Chart, DashaPeriod, Fact

SIGN_YEARS = (7, 16, 9, 21, 5, 9, 16, 7, 10, 4, 4, 10)
GROUP_STARS = ({0, 2, 6, 8, 12, 14, 18, 20, 24}, {1, 7, 13, 19, 25, 26}, {3, 9, 15, 21},
               {4, 5, 10, 11, 16, 17, 22, 23})  # 0-based nakshatras: savya 1, savya 2, apasavya 1, apasavya 2
CYCLES = (
    ((0, 1, 2, 3, 4, 5, 6, 7, 8), (9, 10, 11, 7, 6, 5, 3, 4, 2), (1, 0, 11, 10, 9, 8, 0, 1, 2), (3, 4, 5, 6, 7, 8, 9, 10, 11)),
    ((7, 6, 5, 3, 4, 2, 1, 0, 11), (10, 9, 8, 0, 1, 2, 3, 4, 5), (6, 7, 8, 9, 10, 11, 7, 6, 5), (3, 4, 2, 1, 0, 11, 10, 9, 8)),
    ((8, 9, 10, 11, 0, 1, 2, 4, 3), (5, 6, 7, 11, 10, 9, 8, 7, 6), (5, 4, 3, 2, 1, 0, 8, 9, 10), (11, 0, 1, 2, 4, 3, 5, 6, 7)),
    ((11, 10, 9, 8, 7, 6, 5, 4, 3), (2, 1, 0, 8, 9, 10, 11, 0, 1), (2, 4, 3, 5, 6, 7, 11, 10, 9), (8, 7, 6, 5, 4, 3, 2, 1, 0)),
)
PAIR = {0: 1, 1: 0, 2: 3, 3: 2}  # after the 4th pada the cycle moves to the paired group


def _next(group: int, pada: int) -> tuple[int, int]:
    return (PAIR[group], 0) if pada == 3 else (group, pada + 1)


def periods(chart: Chart, depth: int = 2, years: float = 120) -> list[DashaPeriod]:
    n, pada, frac = nakshatra(chart.bodies["Moon"].lon)  # frac is within the nakshatra
    pada -= 1
    group = next(g for g, stars in enumerate(GROUP_STARS) if n in stars)
    pada_frac = frac * 4 - pada
    cycle = CYCLES[group][pada]
    elapsed = pada_frac * sum(SIGN_YEARS[x] for x in cycle)
    yd = chart.config.dasha_year_days

    # locate the running sign; start the clock at the beginning of the current cycle
    t = chart.utc - timedelta(days=elapsed * yd)
    out, total = [], -elapsed
    while total < years:
        for i, x in enumerate(cycle):
            def children(lords, y, cyc=cycle, i=i):
                rot = cyc[i:] + cyc[:i] if len(lords) == 1 else cyc  # deeper levels: plain proportional split
                tot = sum(SIGN_YEARS[c] for c in rot)
                return [(SIGNS[c], y * SIGN_YEARS[c] / tot) for c in rot]
            ps = split((SIGNS[x],), t, SIGN_YEARS[x], yd, depth, children)
            t = ps[0].end
            total += SIGN_YEARS[x]
            out += ps if ps[0].end > chart.utc else []
        group, pada = _next(group, pada)
        cycle = CYCLES[group][pada]
    return out


def build(chart: Chart) -> list[Fact]:
    return facts("kalachakra", chart, periods(chart))
