"""Layer 1: the fact graph. Typed index over Facts plus the query API the DSL will use."""

from collections import defaultdict
from datetime import datetime

from jyotish_kit.facts.builders import (ashtakavarga, avasthas, aspects, dignity, jaimini, kp, lordships, panchanga,
                                   placements, shadbala, structure)
from jyotish_kit.facts.builders.dashas import kalachakra, rasi, vimshottari, yogini
from jyotish_kit.models import Chart, Fact

BUILDERS = (placements, lordships, aspects, dignity, structure, panchanga, ashtakavarga, avasthas, jaimini, kp, shadbala,
            vimshottari, yogini, rasi, kalachakra)


SOURCES = {
    "placement": "Swiss Ephemeris (apparent geocentric, sidereal per ChartConfig.ayanamsa); vargas BPHS ch.6",
    "lordship": "BPHS ch.3 sign lords; whole-sign houses",
    "aspect": "BPHS ch.26 graha drishti; nodes per ChartConfig.rahu_aspects/ketu_aspects",
    "conjunction": "same sign in the varga",
    "dignity": "BPHS ch.3 (exaltation, moolatrikona, own, panchadha maitri)",
    "relationship": "BPHS ch.3 naisargika + tatkalika = panchadha maitri",
    "combustion": "Surya Siddhanta ch.9 orbs",
    "war": "Surya Siddhanta ch.7 graha yuddha",
    "functional": "BPHS ch.34 general rules (see structure.py)",
    "exchange": "Phaladeepika ch.6 parivartana",
    "argala": "BPHS ch.31 argala",
    "sensitive": "vargottama, gandanta, sandhi, pushkara, mrityu bhaga (see structure.py)",
    "panchanga": "Surya Siddhanta panchanga limbs at the birth moment; avakahada per Muhurta Chintamani",
    "upagraha": "P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach ch.4; BPHS ch.3",
    "ashtakavarga": "BPHS ch.66-70",
    "avastha": "BPHS ch.45 (baladi, jagradadi, deeptadi)",
    "karaka": "Jaimini Upadesa Sutras 1.1; BPHS ch.32 (8 karakas)",
    "arudha": "Jaimini Upadesa Sutras 1.3; BPHS ch.29",
    "special_lagna": "BPHS ch.4 (BL/HL/GL), Jaimini (SL, VL), B.V. Raman (Indu), Bhrigu Bindu",
    "rashi_aspect": "Jaimini Upadesa Sutras 1.1.2-4",
    "kp_lords": "K.S. Krishnamurti, KP Reader (249 subs)",
    "kp_significator": "K.S. Krishnamurti, KP Reader (4-level significators)",
    "shadbala": "BPHS ch.27; B.V. Raman, Graha and Bhava Balas; vimshopaka BPHS ch.7",
    "bhava_bala": "BPHS ch.27; B.V. Raman, Graha and Bhava Balas",
    "dasha_period": "BPHS ch.46-53 (Vimshottari, Yogini, Kalachakra); K.N. Rao (Chara); P.V.R. Narasimha Rao (Narayana)",
}


def build_facts(chart: Chart) -> list[Fact]:
    facts = [f for b in BUILDERS for f in b.build(chart)]
    for f in facts:
        if not f.source:
            f.source = SOURCES.get(f.kind, "")
    return facts


def _is_measure(v) -> bool:
    """Continuous measurements (degrees, dates) are reported as ranges, not compared for stability."""
    return isinstance(v, (float, datetime))


def fact_key(f: Fact):
    """The categorical content of a fact: object plus non-measurement attrs."""
    return f.object, {k: v for k, v in f.attrs.items() if not _is_measure(v)}


def merge_window(nominal: list[Fact], samples: list[list[Fact]]) -> list[Fact]:
    """Tag each nominal fact stable/time_sensitive across the birth-window samples.

    A fact is stable when it exists with identical categorical attrs in every sample.
    Measurement attrs get a `<name>_range` = (min, max) across samples where the fact exists.
    """
    seen: dict[str, list[Fact]] = defaultdict(list)
    for facts in samples:
        for f in facts:
            seen[f.id].append(f)

    out = []
    for f in nominal:
        same = [g for g in seen[f.id] if fact_key(g) == fact_key(f)]
        frac = len(same) / len(samples)
        attrs = dict(f.attrs)
        if len(samples) > 1:
            for k, v in f.attrs.items():
                if _is_measure(v):
                    vals = [g.attrs[k] for g in same]
                    attrs[f"{k}_range"] = (min(vals), max(vals))
        out.append(f.model_copy(update={"stable": frac == 1, "window_fraction": frac, "attrs": attrs}))
    return out


class FactGraph:
    def __init__(self, facts: list[Fact], config=None):
        self.facts = facts
        self.config = config  # ChartConfig the facts were built with (conventions the DSL needs)
        self.by_id = {f.id: f for f in facts}

    def get(self, fact_id: str) -> Fact | None:
        return self.by_id.get(fact_id)

    def query(self, kind: str | None = None, varga: str | None = None,
              subject: str | None = None, object: str | None = None) -> list[Fact]:
        return [f for f in self.facts
                if (kind is None or f.kind == kind) and (varga is None or f.varga == varga)
                and (subject is None or f.subject == subject) and (object is None or f.object == object)]

    def lord_of(self, house: int, varga: str = "D1") -> str:
        return self.by_id[f"lordship:{varga}:H{house}"].object

    def house_of(self, planet: str, varga: str = "D1") -> int:
        return self.by_id[f"placement:{varga}:{planet}"].attrs["house"]

    def sign_of(self, planet: str, varga: str = "D1") -> str:
        return self.by_id[f"placement:{varga}:{planet}"].attrs["sign"]

    def occupants(self, house: int, varga: str = "D1") -> list[str]:
        return [f.subject for f in self.query("placement", varga)
                if f.attrs["house"] == house and f.subject != "Lagna"]

    def aspects_on(self, target: str, varga: str = "D1") -> list[str]:
        """Planets aspecting a planet name or a house ("H7")."""
        return [f.subject for f in self.query("aspect", varga, object=target)]
