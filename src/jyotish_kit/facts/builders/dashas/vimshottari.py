"""Vimshottari dasha (BPHS ch.46) to pratyantar level."""

from datetime import timedelta

from jyotish_kit.facts.builders.nakshatra import DASHA_ORDER, nakshatra
from jyotish_kit.models import Chart, DashaPeriod, Fact, FactKind

YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
         "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}


def _subperiods(lords: tuple[str, ...], start, years: float, year_days: float, depth: int):
    """Yield the period and, recursively, its sub-periods. Sub-periods start from the parent lord."""
    yield DashaPeriod(lords=lords, start=start, end=start + timedelta(days=years * year_days))
    if len(lords) < depth:
        i = DASHA_ORDER.index(lords[-1])
        t = start
        for k in range(9):
            sub = DASHA_ORDER[(i + k) % 9]
            sub_years = years * YEARS[sub] / 120
            yield from _subperiods((*lords, sub), t, sub_years, year_days, depth)
            t += timedelta(days=sub_years * year_days)


def periods(chart: Chart, depth: int = 3) -> list[DashaPeriod]:
    """All periods of the 120-year cycle that begins at the start of the birth mahadasha."""
    n, _, frac = nakshatra(chart.bodies["Moon"].lon)
    first = DASHA_ORDER[n % 9]
    yd = chart.config.dasha_year_days
    t = chart.utc - timedelta(days=frac * YEARS[first] * yd)
    out = []
    i = DASHA_ORDER.index(first)
    for k in range(9):
        lord = DASHA_ORDER[(i + k) % 9]
        out.extend(_subperiods((lord,), t, YEARS[lord], yd, depth))
        t += timedelta(days=YEARS[lord] * yd)
    return out


def active(chart: Chart, start, end, depth: int = 3) -> list[DashaPeriod]:
    """Periods at exactly `depth` levels overlapping [start, end)."""
    return [p for p in periods(chart, depth) if len(p.lords) == depth and p.start < end and p.end > start]


def balance_at_birth(chart: Chart) -> tuple[str, float]:
    """(birth mahadasha lord, years remaining at birth)."""
    n, _, frac = nakshatra(chart.bodies["Moon"].lon)
    lord = DASHA_ORDER[n % 9]
    return lord, (1 - frac) * YEARS[lord]


def build(chart: Chart) -> list[Fact]:
    return [
        Fact(id=f"dasha_period:vimshottari:{'/'.join(p.lords)}", kind=FactKind.dasha_period, varga="D1",
             subject=p.lords[-1], attrs={"system": "vimshottari", "level": len(p.lords), "lords": list(p.lords),
                                         "start": p.start, "end": p.end})
        for p in periods(chart) if p.end > chart.utc
    ]
