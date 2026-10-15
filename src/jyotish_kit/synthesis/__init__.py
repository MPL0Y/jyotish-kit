"""Layer 3: fire rules, weigh, apply meta-rules, and judge each topic separately per school.

Schools are never merged: a Judgment is for one (topic, school). Only verified rules are used unless
include_drafts=True, and then every Judgment says so.
"""

from functools import cached_property
from pathlib import Path

import yaml
from pydantic import BaseModel

from jyotish_kit.corpus import fire, load
from jyotish_kit.kundli import Kundli
from jyotish_kit.models import Rule
from jyotish_kit.synthesis import metarules
from jyotish_kit.synthesis.weighting import Weights, weigh

TOPICS_PATH = Path(__file__).parent / "topics.yaml"
CONFIG = yaml.safe_load(TOPICS_PATH.read_text())
TOPICS: dict[str, dict] = CONFIG["topics"]
NO_RULE = "no rule in corpus covers this"
NONE_FIRED = "no rule in corpus fired for this"  # rules exist for the topic; none hold on this chart


class Evidence(BaseModel):
    rule_id: str
    name: str
    school: str
    status: str
    polarity: int
    domains: list[str]
    themes: list[str]
    weight: float
    factors: dict[str, float]
    matched: list[str]
    citation: str
    timing: str | None = None
    adjustments: list[str] = []

    @property
    def signed(self) -> float:
        return self.polarity * self.weight

    def adjust(self, factor: float, why: str) -> None:
        self.weight *= factor
        self.adjustments.append(f"x{factor:g}: {why}")


class Judgment(BaseModel):
    topic: str
    school: str
    score: float
    verdict: str  # favourable | mixed | adverse | NO_RULE | NONE_FIRED
    confidence: float
    triple: dict
    varga: dict
    supporting: list[Evidence]
    opposing: list[Evidence]
    evidence: list[Evidence]
    drafts: bool
    notes: list[str] = []


THRESHOLD = 1.0  # |score| at which a verdict leaves "mixed"
CONFIDENCE = {"confirmed": 1.0, "partial": 0.7, "insufficient": 0.5, "conflicting": 0.4,
              "supports": 1.0, "neutral": 0.85, "denies": 0.6, "not applicable": 1.0}


def _citation(r: Rule) -> str:
    s = r.source
    return f"{s.text} ch.{s.chapter}" + (f" v.{s.verse}" if s.verse else "") + f" ({s.edition})"


class Synthesis:  # rules tagged `timing` say when, not whether: they feed Layer 4 only
    """All evidence for one chart, built once; judge() slices it per topic and school."""

    def __init__(self, k: Kundli, include_drafts: bool = False, weights: Weights | None = None,
                 schools: tuple[str, ...] = ("parashari", "jaimini", "kp")):
        self.k, self.drafts, self.w, self.schools = k, include_drafts, weights or Weights(), schools
        self.rules = {r.id: r for r in load(include_drafts=include_drafts)
                      if r.school in schools and (include_drafts or r.status == "verified")}

    @cached_property
    def evidence(self) -> list[Evidence]:
        facts, out = self.k.facts, []
        for r in self.rules.values():
            f = fire(r, facts)
            if not f.fired:
                continue
            w, factors = weigh(r, f.matched, facts, self.w)
            out.append(Evidence(rule_id=r.id, name=r.name, school=r.school, status=r.status,
                                polarity=r.effect.polarity, domains=r.effect.domains, themes=r.effect.themes,
                                weight=w, factors=factors, matched=f.matched, citation=_citation(r),
                                timing=r.timing))
        metarules.precedence(out, self.rules, CONFIG["precedence"])
        metarules.alternatives(out, self.rules)
        metarules.neecha_bhanga(out, self.rules, facts, self.w)
        metarules.functional_nature(out, facts, self.w)
        return out

    def judge(self, topic: str, school: str) -> Judgment:
        t = TOPICS[topic]
        ev = sorted((e for e in self.evidence if e.school == school and set(e.domains) & set(t["domains"])
                     and e.weight > 0 and "timing" not in self.rules[e.rule_id].tags), key=lambda e: -abs(e.signed))
        score = round(sum(e.signed for e in ev), 3)
        notes = []
        if self.drafts:
            notes.append("uses unverified draft rules")
        if not any(r.school == school and set(r.effect.domains) & set(t["domains"]) for r in self.rules.values()):
            return Judgment(topic=topic, school=school, score=0, verdict=NO_RULE, confidence=0, triple={},
                            varga={}, supporting=[], opposing=[], evidence=[], drafts=self.drafts,
                            notes=notes + [f"no {'' if self.drafts else 'verified '}{school} rule for {topic}"])
        tri = (metarules.triple(self.k.facts, t, CONFIG["triple"]) if school == "parashari"
               else {"status": "not applicable"})
        vc = (metarules.varga(self.k.facts, t, CONFIG["varga_confirmation"]) if school == "parashari"
              else {"status": "not applicable"})
        verdict = ("favourable" if score >= THRESHOLD else "adverse" if score <= -THRESHOLD else "mixed") if ev \
            else NONE_FIRED
        if score > 0 and vc["status"] == "denies":
            notes.append(f"D1 promise not supported in {vc['varga']}: results nominal")
        # agreement: share of the evidence weight on the side of the verdict (1 when all evidence points one way)
        total = sum(abs(e.signed) for e in ev)
        agreement = abs(score) / total if total else 0.0
        conf = agreement * CONFIDENCE.get(tri["status"], 1.0) * (CONFIDENCE.get(vc["status"], 1.0) if score > 0 else 1.0)
        return Judgment(topic=topic, school=school, score=score, verdict=verdict, confidence=round(conf, 2),
                        triple=tri, varga=vc, supporting=[e for e in ev if e.polarity > 0][:5],
                        opposing=[e for e in ev if e.polarity < 0][:5], evidence=ev, drafts=self.drafts,
                        notes=notes)

    def judge_all(self, topics=None) -> dict[str, dict[str, Judgment]]:
        return {t: {s: self.judge(t, s) for s in self.schools} for t in (topics or TOPICS)}
