"""Meta-rules applied over fired evidence. Each says where it comes from.

- alternatives:      rules tagged alt:<group> state one result several ways; the strongest counts once.
- precedence:        Nabhasa sankhya yogas yield to the other Nabhasa groups (topics.yaml `precedence`).
- neecha_bhanga:     adverse evidence resting on a debilitated planet is softened when a neecha bhanga
                     rule fired for that planet (Phaladeepika ch.7).
- functional_nature: favourable evidence resting only on functional malefics for the Lagna (or adverse only
                     on functional benefics) is discounted (BPHS ch.34; predicates functional_benefic/malefic).
- triple:            a topic is confirmed only when bhava, bhavesh and karaka agree (BPHS ch.11);
                     each is read from the chart by the templates in topics.yaml.
- varga:             the D1 promise must be supported in the topic's varga (BPHS ch.6-7).
"""

from jyotish_kit.dsl.evaluator import DSLError, evaluate
from jyotish_kit.facts.graph import FactGraph
from jyotish_kit.synthesis.weighting import Weights, involved


def precedence(evidence: list, rules: dict, table: list[dict]) -> None:
    fired_tags = {t for e in evidence if e.weight > 0 for t in rules[e.rule_id].tags}
    for row in table:
        if fired_tags & set(row["to"]):
            for e in evidence:
                if row["yields"] in rules[e.rule_id].tags:
                    e.adjust(0.0, f"yields to {'/'.join(sorted(fired_tags & set(row['to'])))} ({row['source']})")


def alternatives(evidence: list, rules: dict) -> None:
    """Rules tagged alt:<group> are alternative conditions for one result (e.g. the neecha bhanga variants):
    only the strongest fired one counts per group and chart."""
    # ponytail: one group per chart, so two debilitated planets each with neecha bhanga count once; key the
    # group by planet if that case matters
    groups: dict[str, list] = {}
    for e in evidence:
        for t in rules[e.rule_id].tags:
            if t.startswith("alt:"):
                groups.setdefault(t, []).append(e)
    for g, es in groups.items():
        best = max(es, key=lambda e: e.weight)
        for e in es:
            if e is not best:
                e.adjust(0.0, f"alternative to {best.rule_id} ({g}): counted once")


def neecha_bhanga(evidence: list, rules: dict, facts: FactGraph, w: Weights) -> None:
    def debilitated(e):
        return {fid.split(":")[2] for fid in e.matched
                if fid.startswith("dignity:") and (f := facts.get(fid)) and f.attrs["status"] == "debilitated"}
    rescued = set().union(*(debilitated(e) for e in evidence if "neecha_bhanga" in rules[e.rule_id].tags and e.weight))
    for e in evidence:
        hit = debilitated(e) & rescued
        if e.polarity < 0 and hit:
            e.adjust(w.neecha_bhanga, f"neecha bhanga of {', '.join(sorted(hit))} (Phaladeepika ch.7)")


def functional_nature(evidence: list, facts: FactGraph, w: Weights) -> None:
    cache: dict[tuple[str, str], bool] = {}

    def is_(kind, p):
        if (kind, p) not in cache:
            try:
                cache[kind, p] = bool(evaluate(f"functional_{kind}({p})", facts, school="parashari")[0])
            except DSLError:
                cache[kind, p] = False
        return cache[kind, p]
    for e in evidence:
        if e.school != "parashari" or not e.polarity:
            continue
        ps = involved(e.matched, facts)
        kind = "malefic" if e.polarity > 0 else "benefic"
        if ps and all(is_(kind, p) for p in ps):
            e.adjust(w.functional, f"rests only on functional {kind}s {', '.join(ps)} for this Lagna (BPHS ch.34)")


def _sign(facts, plus: str, minus: str, varga: str = "D1") -> int:
    if evaluate(plus, facts, varga=varga, school="parashari")[0]:
        return 1
    return -int(bool(evaluate(minus, facts, varga=varga, school="parashari")[0]))


def triple(facts: FactGraph, topic: dict, conf: dict) -> dict:
    """Bhava, bhavesh and karaka each read +1/-1/0 from the chart; confirmed only when all three agree."""
    h = topic["house"]
    g = conf["graha"]
    comp = {"bhava": _sign(facts, conf["bhava"]["plus"].format(h=h), conf["bhava"]["minus"].format(h=h)),
            "bhavesh": _sign(facts, g["plus"].format(p=facts.lord_of(h)), g["minus"].format(p=facts.lord_of(h)))}
    ks = [_sign(facts, g["plus"].format(p=k), g["minus"].format(p=k)) for k in topic["karakas"]]
    comp["karaka"] = (sum(ks) > 0) - (sum(ks) < 0)
    vals = list(comp.values())
    status = ("confirmed" if len(set(vals)) == 1 and vals[0] else
              "conflicting" if 1 in vals and -1 in vals else "partial" if vals.count(0) == 1 else "insufficient")
    return {"components": comp, "status": status,
            "reading": "favourable" if sum(vals) > 0 else "adverse" if sum(vals) < 0 else "neutral"}


def varga(facts: FactGraph, topic: dict, conf: dict) -> dict:
    v = topic["varga"]
    if v == "D1":
        return {"varga": v, "status": "not applicable", "planets": {}}
    out = {}
    lord = facts.lord_of(topic["house"], v)
    for p in dict.fromkeys([lord, *topic["karakas"]]):
        sup = evaluate(conf["supports"].format(p=p), facts, varga=v, school="parashari")
        den = evaluate(conf["denies"].format(p=p), facts, varga=v, school="parashari")
        out[p] = "supports" if sup[0] else "denies" if den[0] else "neutral"
    vals = list(out.values())
    status = ("supports" if vals.count("supports") > vals.count("denies")
              else "denies" if vals.count("denies") > vals.count("supports") else "neutral")
    return {"varga": v, "status": status, "planets": out}
