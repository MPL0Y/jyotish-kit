"""Yogini dasha: 8 yoginis, 36-year cycle, from the Moon's nakshatra ((n + 3) mod 8, Ashwini -> Bhramari)."""

from datetime import timedelta

from jyotish_kit.facts.builders.dashas import facts, split
from jyotish_kit.facts.builders.nakshatra import nakshatra
from jyotish_kit.models import Chart, DashaPeriod, Fact

YOGINIS = (("Mangala", "Moon", 1), ("Pingala", "Sun", 2), ("Dhanya", "Jupiter", 3), ("Bhramari", "Mars", 4),
           ("Bhadrika", "Mercury", 5), ("Ulka", "Saturn", 6), ("Siddha", "Venus", 7), ("Sankata", "Rahu", 8))
LORDS = [y[1] for y in YOGINIS]
YEARS = {y[1]: y[2] for y in YOGINIS}
NAMES = {y[1]: y[0] for y in YOGINIS}


def _children(lords, years):
    i = LORDS.index(lords[-1])
    return [(LORDS[(i + k) % 8], years * YEARS[LORDS[(i + k) % 8]] / 36) for k in range(8)]


def periods(chart: Chart, depth: int = 2, cycles: int = 4) -> list[DashaPeriod]:
    n, _, frac = nakshatra(chart.bodies["Moon"].lon)  # n is 0-based
    i = (n + 1 + 3) % 8 - 1
    first = LORDS[i]
    yd = chart.config.dasha_year_days
    t = chart.utc - timedelta(days=frac * YEARS[first] * yd)
    out = []
    for k in range(8 * cycles):
        lord = LORDS[(i + k) % 8]
        out += split((lord,), t, YEARS[lord], yd, depth, _children)
        t += timedelta(days=YEARS[lord] * yd)
    return out


def build(chart: Chart) -> list[Fact]:
    return facts("yogini", chart, periods(chart))
