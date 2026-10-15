"""Layer 4: when a promised topic is activated. Scores every Vimshottari pratyantar period and returns the
best few windows with their drivers; never a single date.

A period can only activate what the chart promises: when the topic's natal judgment is not favourable the
result says so, and the windows read as attempts or pressure on the matter, not fulfilment.

Sources (weights in Activation):
- dasha lords' connection to the topic: topics.yaml `activation` templates per school, per lord level;
- the same connection read in the topic's varga (D9 for marriage, D10 for career, ...): lord, occupant, aspect;
- the rules of the topic whose `timing` expression holds for the running lords;
- Parashari only: Jupiter-Saturn double transit on the house or its lord's sign, the transiting
  Jupiter/Saturn's bindus in their own BAV, and the varshaphal (muntha in the house, year lord = its lord).
Jaimini timing (chara dasha) is not modelled yet; KP uses only significators (no transits).
"""

from datetime import datetime

from pydantic import BaseModel

from jyotish_kit.corpus import timing_active
from jyotish_kit.dsl.evaluator import evaluate
from jyotish_kit.facts import varshaphal
from jyotish_kit.facts.builders.dashas.vimshottari import active
from jyotish_kit.facts.transits import transit_facts
from jyotish_kit.synthesis import CONFIG, NO_RULE, NONE_FIRED, TOPICS, Synthesis

YEAR = 365.2425


class Activation(BaseModel):
    levels: dict[str, float] = {"dasha_lord": 0.5, "antardasha_lord": 1.0, "pratyantardasha_lord": 0.5}
    rule: float = 0.5           # x the rule's signed natal weight
    double_transit: float = 1.0
    bav_good: int = 4           # transiting Jupiter/Saturn with >= this many bindus in its own BAV helps
    bav: float = 0.25
    muntha: float = 0.5
    year_lord: float = 0.5
    varga: float = 0.5          # x the template weight, for connections in the topic's varga (D9, D10, ...)
    varga_templates: tuple[str, ...] = ("lord of the house", "occupies the house", "aspects the house")
    # periods scoring >= floor + keep x (best - floor) are merged into windows; the floor (the lowest period
    # score in the range) removes what is constant across it, such as one mahadasha spanning the whole range
    keep: float = 0.6


class TimeWindow(BaseModel):
    start: datetime
    end: datetime
    score: float
    lords: list[str]          # the peak period's lords
    drivers: list[str]


class Timing(BaseModel):
    topic: str
    school: str
    promise: str
    promise_score: float
    windows: list[TimeWindow]
    notes: list[str] = []


def _fmt(expr: str, **kw) -> str:
    return expr.format(**{k: (f"[{', '.join(map(str, v))}]" if isinstance(v, list) else v) for k, v in kw.items()})


def windows(syn: Synthesis, topic: str, school: str, start: datetime, end: datetime, top: int = 5,
            a: Activation | None = None) -> Timing:
    a = a or Activation()
    k, t = syn.k, TOPICS[topic]
    facts, h = k.facts, t["house"]
    j = syn.judge(topic, school)
    notes = list(j.notes)
    if j.verdict in (NO_RULE, NONE_FIRED):
        return Timing(topic=topic, school=school, promise=j.verdict, promise_score=0, windows=[],
                      notes=notes + ["no natal promise can be judged, so no timing is given"])
    if school == "jaimini":
        return Timing(topic=topic, school=school, promise=j.verdict, promise_score=j.score, windows=[],
                      notes=notes + ["Jaimini timing (chara dasha) is not modelled yet"])
    if j.verdict != "favourable":
        notes.append(f"natal promise is {j.verdict} ({j.score:+.2f}): these periods activate the matter, "
                     "they do not by themselves promise a good outcome")
    scored = score_periods(syn, topic, school, start, end, a)
    best = max((x[1] for x in scored), default=0)
    floor = min(x[1] for x in scored) if scored else 0
    if best <= 0 or best == floor:
        return Timing(topic=topic, school=school, promise=j.verdict, promise_score=j.score, windows=[],
                      notes=notes + ["no period in the range activates this topic"])
    out: list[TimeWindow] = []
    for per, s, drv, _ in scored:
        if s < floor + a.keep * (best - floor):
            continue
        if out and out[-1].end >= per.start:
            w = out[-1]
            w.end = per.end
            if s > w.score:
                w.score, w.lords, w.drivers = s, list(per.lords), drv
        else:
            out.append(TimeWindow(start=per.start, end=per.end, score=s, lords=list(per.lords), drivers=drv))
    out = sorted(sorted(out, key=lambda w: -w.score)[:top], key=lambda w: w.start)
    return Timing(topic=topic, school=school, promise=j.verdict, promise_score=j.score, windows=out, notes=notes)


SOURCES = ("dasha", "varga", "rules", "transit", "bav", "varsha")


def score_periods(syn: Synthesis, topic: str, school: str, start: datetime, end: datetime,
                  a: Activation | None = None, sources: tuple[str, ...] = SOURCES) -> list[tuple]:
    """(period, score, drivers, parts) for every Vimshottari pratyantar overlapping [start, end);
    parts is the score split by source, so the backtest can tell which source carries signal."""
    a = a or Activation()
    k, t = syn.k, TOPICS[topic]
    facts, h = k.facts, t["house"]
    templates = CONFIG["activation"][school]
    rules = [r for r in syn.rules.values() if r.school == school and r.timing
             and set(r.effect.domains) & set(t["domains"])]
    fired = {e.rule_id: e for e in syn.evidence} if "rules" in sources else {}
    # timing-only rules (condition true or promise-gated) still need their condition to have fired
    rules = [r for r in rules if r.id in fired]
    lord_h = facts.lord_of(h)
    periods = active(k.chart, start, end)
    varga = t["varga"] if school == "parashari" and t["varga"] != "D1" and "varga" in sources else None

    def connect(p, v="D1", only=None):
        return [(tp["name"], tp["w"]) for tp in templates if (only is None or tp["name"] in only)
                and evaluate(_fmt(tp["expr"], p=p, h=h, karakas=t["karakas"], **t["kp"]), facts, varga=v,
                             school=school)[0]]
    lords_all = {x for per in periods for x in per.lords}
    conn = {p: connect(p) for p in lords_all}
    vconn = {p: connect(p, varga, a.varga_templates) for p in lords_all} if varga else {}
    annual: dict[int, list] = {}
    scored = []
    for per in periods:
        lords = dict(zip(a.levels, per.lords))
        parts = dict.fromkeys(sources, 0.0)
        drivers = []
        for lvl, p in lords.items():
            if "dasha" in sources:
                for name, w in conn[p]:
                    parts["dasha"] += w * a.levels[lvl]
                    drivers.append(f"{lvl.split('_')[0]} {p}: {name}")
            for name, w in vconn.get(p, []):
                parts["varga"] += a.varga * w * a.levels[lvl]
                drivers.append(f"{lvl.split('_')[0]} {p}: {name} in {varga}")
        if "rules" in sources:
            for r in rules:
                ok, _ = timing_active(r, facts, lords)
                if ok and fired[r.id].signed:
                    parts["rules"] += a.rule * fired[r.id].signed
                    drivers.append(f"rule {r.id} ({fired[r.id].signed:+.2f})")
        if school == "parashari" and {"transit", "bav", "varsha"} & set(sources):
            mid = per.start + (per.end - per.start) / 2
            if {"transit", "bav"} & set(sources):
                tr = {f.id.split(":", 2)[2]: f for f in transit_facts(k.chart, mid)}
            if "transit" in sources:
                lord_house = facts.house_of(lord_h)
                for hh, what in ((h, f"house {h}"), (lord_house, f"its lord's house {lord_house}")):
                    if f"double_transit:H{hh}" in tr:
                        parts["transit"] += a.double_transit
                        drivers.append(f"Jupiter-Saturn double transit on {what}")
                        break
            if "bav" in sources:
                for p in ("Jupiter", "Saturn"):
                    b = tr[p].attrs["bav_bindus"]
                    parts["bav"] += a.bav if b >= a.bav_good else -a.bav
                    drivers.append(f"transit {p} in {tr[p].attrs['sign']} with {b} bindus")
            if "varsha" in sources:
                n = int((mid - k.chart.utc).days // YEAR)
                if n not in annual:
                    annual[n] = varshaphal.facts(k.chart, n)
                vf = {f.id.split(":")[2]: f for f in annual[n] if f.id.count(":") == 2}
                if vf["muntha"].attrs["house"] == h:
                    parts["varsha"] += a.muntha
                    drivers.append(f"varsha {n}: muntha in house {h}")
                if vf["year_lord"].object == lord_h:
                    parts["varsha"] += a.year_lord
                    drivers.append(f"varsha {n}: year lord {lord_h} rules house {h}")
        scored.append((per, round(sum(parts.values()), 3), drivers, {k_: round(v, 3) for k_, v in parts.items()}))
    return scored
