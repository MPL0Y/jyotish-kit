"""Dasha systems. Each module exposes periods(chart, depth) -> list[DashaPeriod] and build(chart)."""

from datetime import timedelta

from jyotish_kit.models import Chart, DashaPeriod, Fact, FactKind


def split(lords: tuple[str, ...], start, years: float, year_days: float, depth: int, children) -> list[DashaPeriod]:
    """The period plus its sub-periods down to `depth`. children(lords, years) -> [(sub_lord, sub_years)]."""
    out = [DashaPeriod(lords=lords, start=start, end=start + timedelta(days=years * year_days))]
    if len(lords) < depth:
        t = start
        for sub, sub_years in children(lords, years):
            out += split((*lords, sub), t, sub_years, year_days, depth, children)
            t += timedelta(days=sub_years * year_days)
    return out


def facts(system: str, chart: Chart, periods: list[DashaPeriod]) -> list[Fact]:
    """Ids are unique: a lord sequence repeated in a later cycle gets "@<cycle>" (2, 3, ...)."""
    out, seen = [], {}
    for p in periods:
        key = "/".join(p.lords)
        seen[key] = seen.get(key, 0) + 1
        if p.end > chart.utc and p.end > p.start:
            suffix = f"@{seen[key]}" if seen[key] > 1 else ""
            out.append(Fact(id=f"dasha_period:{system}:{key}{suffix}", kind=FactKind.dasha_period, varga="D1",
                            subject=p.lords[-1], attrs={"system": system, "level": len(p.lords),
                                                        "lords": list(p.lords), "start": p.start, "end": p.end}))
    return out
