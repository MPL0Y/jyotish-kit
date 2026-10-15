"""Layer 6: backtest and rectification. Both only report; nothing here edits rules or weights.

An event is matched against what ran "around" it: its span (LifeEvent.span) widened by `pad` days on each
side. Every figure is compared with a baseline: the same-length window slid across the life so far (birth to
`until`) in `STEP`-day steps. A rule's lift is its hit rate over that baseline rate. A timing source's
percentile is where the event's window ranks among all the slid windows: 0.5 on average means no signal.
"""

import random
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta, timezone
from functools import cache
from math import sqrt
from statistics import mean

from pydantic import BaseModel

from jyotish_kit.corpus import timing_active
from jyotish_kit.facts.builders.dashas.vimshottari import active
from jyotish_kit.facts.builders.vargas import varga_sign
from jyotish_kit.feedback.events import topic_of
from jyotish_kit.kundli import Kundli
from jyotish_kit.models import SIGNS, BirthData, LifeEvent
from jyotish_kit.synthesis import CONFIG, TOPICS, Synthesis
from jyotish_kit.timing import SOURCES, Activation, score_periods

STEP = 7
LEVELS = list(Activation().levels)


class Series:
    """A per-day value over [origin, until], from Vimshottari periods; window queries take the max."""

    def __init__(self, periods: list[tuple], origin: date, until: date):
        self.origin, self.v = origin, [0.0] * ((until - origin).days + 1)
        for per, val in periods:
            a = max((per.start.date() - origin).days, 0)
            b = min((per.end.date() - origin).days, len(self.v) - 1)
            for i in range(a, b + 1):
                self.v[i] = max(self.v[i], val) if i == a else val  # boundary day: either period counts

    def at(self, d0: date, d1: date) -> float:
        a, b = max((d0 - self.origin).days, 0), min((d1 - self.origin).days, len(self.v) - 1)
        return max(self.v[a:b + 1])

    def baseline(self, length: int) -> list[float]:
        return [max(self.v[i:i + length]) for i in range(0, len(self.v) - length + 1, STEP)]

    @cache
    def _sorted(self, length: int) -> list[float]:
        return sorted(self.baseline(length))

    def pct(self, d0: date, d1: date) -> float:
        """Percentile of the window [d0, d1] among all same-length windows (ties count half)."""
        dist, x = self._sorted((d1 - d0).days + 1), self.at(d0, d1)
        lo, hi = bisect_left(dist, x), bisect_right(dist, x)
        return round((lo + 0.5 * (hi - lo)) / len(dist), 3)

    def varies(self) -> bool:
        return min(self.v) != max(self.v)


def _window(e: LifeEvent, pad: int) -> tuple[date, date]:
    d0, d1 = e.span()
    return d0 - timedelta(days=pad), d1 + timedelta(days=pad)


def z_score(pcts: list[float]) -> float:
    """Mean percentile against chance (uniform: mean 0.5, sd sqrt(1/12n)); ties make it conservative."""
    return (mean(pcts) - 0.5) / sqrt(1 / (12 * len(pcts))) if pcts else 0.0


class RuleResult(BaseModel):
    rule_id: str
    school: str
    topic: str
    events: int
    hits: int
    baseline: float  # chance of a hit for a window of the same length, averaged over the events
    lift: float | None  # (hits / events) / baseline; None when the condition is never active


class EventResult(BaseModel):
    description: str
    date: date
    topic: str
    school: str
    percentile: dict[str, float]  # per source, and "total"
    period: str  # lords running at the event's start


class Backtest(BaseModel):
    rules: list[RuleResult]
    events: list[EventResult]
    sources: dict[str, dict[str, tuple[float, float]]]  # school -> source -> (mean percentile, z)
    schools: dict[str, tuple[int, int, float, float | None]]  # school -> (events, hits, baseline, lift)
    skipped: list[str]  # events with no topic, or outside the range


def backtest(syn: Synthesis, evs: list[LifeEvent], until: date | None = None, pad: int = 30) -> Backtest:
    k = syn.k
    origin, until = k.chart.utc.date(), until or date.today()
    t0, t1 = k.chart.utc, datetime.combine(until, datetime.min.time(), timezone.utc)
    periods = active(k.chart, t0, t1)
    rules, events, skipped = [], [], []
    by_topic: dict[str, list[LifeEvent]] = {}
    for e in evs:
        t = topic_of(e.domain)
        if t is None or e.span()[1] > until:
            skipped.append(f"{e.date} {e.domain}: " + ("no topic" if t is None else "after the backtest range"))
        else:
            by_topic.setdefault(t, []).append(e)
    fired = {x.rule_id for x in syn.evidence}
    schools_ = [s for s in syn.schools if s in CONFIG["activation"]]
    skipped += [f"{s} school: timing not modelled" for s in syn.schools if s not in schools_]
    for school in schools_:
        for topic, tevs in by_topic.items():
            scored = score_periods(syn, topic, school, t0, t1)
            series = {s: Series([(p, parts[s]) for p, _, _, parts in scored], origin, until)
                      for s in SOURCES}
            series["total"] = Series([(p, sc) for p, sc, _, _ in scored], origin, until)
            series = {s: x for s, x in series.items() if x.varies()}  # a source a school does not use stays out
            for e in tevs:
                d0, d1 = _window(e, pad)
                lords = next((p.lords for p in periods if p.start.date() <= e.span()[0] < p.end.date()), [])
                events.append(EventResult(
                    description=e.description, date=e.date, topic=topic, school=school, period="/".join(lords),
                    percentile={s: ser.pct(d0, d1) for s, ser in series.items()}))
            doms = set(TOPICS[topic]["domains"])
            for r in syn.rules.values():
                if r.school != school or not r.timing or r.id not in fired or not set(r.effect.domains) & doms:
                    continue
                ser = Series([(p, float(timing_active(r, k.facts, dict(zip(LEVELS, p.lords)))[0])) for p in periods],
                             origin, until)
                hits, bases = 0, []
                for e in tevs:
                    d0, d1 = _window(e, pad)
                    hits += ser.at(d0, d1) > 0
                    bases.append(mean(ser.baseline((d1 - d0).days + 1)))
                base = mean(bases)
                rules.append(RuleResult(rule_id=r.id, school=school, topic=topic, events=len(tevs), hits=hits,
                                        baseline=round(base, 3),
                                        lift=round(hits / len(tevs) / base, 2) if base else None))
    sources, schools = {}, {}
    for school in schools_:
        evs_s = [x for x in events if x.school == school]
        names = dict.fromkeys(s for x in evs_s for s in x.percentile)
        sources[school] = {s: (round(mean(ps), 3), round(z_score(ps), 2))
                           for s in names for ps in [[x.percentile[s] for x in evs_s if s in x.percentile]]}
        rs = [r for r in rules if r.school == school]
        n, h = sum(r.events for r in rs), sum(r.hits for r in rs)
        b = sum(r.baseline * r.events for r in rs) / n if n else 0.0
        schools[school] = (n, h, round(b, 3), round(h / n / b, 2) if n and b else None)
    return Backtest(rules=sorted(rules, key=lambda r: (r.school, -(r.lift or 0))), events=events,
                    sources=sources, schools=schools, skipped=skipped)


class Candidate(BaseModel):
    offset_min: float
    dt_local: datetime
    score: float  # mean percentile of the events' activation, over all events
    z: float
    lagna: dict[str, str]  # D1/D9/D10 lagna sign
    percentiles: list[float]


class Rectification(BaseModel):
    candidates: list[Candidate]  # best first
    null_best: list[float]  # best candidate score for each set of randomly re-dated events
    p_value: float  # share of random sets whose best candidate scores >= the real best


def rectify(birth: BirthData, evs: list[LifeEvent], window_min: float | None = None, step_min: float = 1,
            school: str = "parashari", sources: tuple[str, ...] = ("dasha", "varga"), until: date | None = None,
            pad: int = 30, null: int = 200, seed: int = 0) -> Rectification:
    """Score birth times across +/- window_min (default: the stated uncertainty, at least 30 minutes) by how
    strongly each event's topic is activated by Vimshottari lords (in D1 and the topic's varga, where the
    D9/D10 lagna changes show up) when it happened. A ranking to inspect, never an answer.

    The best of many candidates scores well by chance, so the same search is rerun on `null` sets of the same
    events moved to random dates; p_value says how often chance alone did as well as the real events."""
    w = window_min if window_min is not None else max(birth.time_uncertainty_min, 30)
    until = until or date.today()
    evs = [(e, topic_of(e.domain)) for e in evs if topic_of(e.domain) and e.span()[1] <= until]
    origin = birth.dt_local.date()
    rng = random.Random(seed)
    life = (until - origin).days
    shams = [[(t, *_shift(e, pad, origin, rng.randrange(life - (e.span()[1] - e.span()[0]).days - 2 * pad)))
              for e, t in evs] for _ in range(null)]
    out, null_scores = [], [[] for _ in range(null)]
    steps = int(round(w / step_min))
    for i in range(-steps, steps + 1):
        off = i * step_min
        b = birth.model_copy(update={"dt_local": birth.dt_local + timedelta(minutes=off), "time_uncertainty_min": 0})
        k = Kundli.from_birth(b)
        syn = Synthesis(k, schools=(school,))
        t0, t1 = k.chart.utc, datetime.combine(until, datetime.min.time(), timezone.utc)
        series = {t: Series([(p, sc) for p, sc, _, _ in score_periods(syn, t, school, t0, t1, sources=sources)],
                            origin, until) for t in {t for _, t in evs}}
        pcts = [series[t].pct(*_window(e, pad)) for e, t in evs]
        for j, sham in enumerate(shams):
            null_scores[j].append(mean(series[t].pct(d0, d1) for t, d0, d1 in sham))
        lon = k.chart.bodies["Lagna"].lon
        out.append(Candidate(offset_min=off, dt_local=b.dt_local, score=round(mean(pcts), 3) if pcts else 0,
                             z=round(z_score(pcts), 2), percentiles=pcts,
                             lagna={v: SIGNS[varga_sign(lon, v)] for v in ("D1", "D9", "D10")}))
    out.sort(key=lambda c: (-c.score, abs(c.offset_min)))
    null_best = sorted(round(max(x), 3) for x in null_scores)
    best = out[0].score if out else 0
    return Rectification(candidates=out, null_best=null_best,
                         p_value=round(sum(x >= best for x in null_best) / len(null_best), 3) if null_best else 1.0)


def _shift(e: LifeEvent, pad: int, origin: date, start: int) -> tuple[date, date]:
    d0, d1 = _window(e, pad)
    s = origin + timedelta(days=start)
    return s, s + (d1 - d0)
