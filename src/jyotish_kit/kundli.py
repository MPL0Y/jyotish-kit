from jyotish_kit.config import ChartConfig
from jyotish_kit.ephemeris.engine import compute
from jyotish_kit.ephemeris.uncertainty import compute_window, window_offsets
from jyotish_kit.facts.builders.dashas import vimshottari
from jyotish_kit.facts.graph import FactGraph, build_facts, merge_window, fact_key
from jyotish_kit.models import BirthData, Chart, DashaPeriod


class Kundli:
    def __init__(self, birth: BirthData, config: ChartConfig, step_sec: float | None = None):
        self.birth, self.config = birth, config
        charts = compute_window(birth, config, step_sec)
        self.charts = charts
        self.chart: Chart = charts[window_offsets(birth, step_sec).index(0)]
        samples = [build_facts(c) for c in charts]
        self.facts = FactGraph(merge_window(build_facts(self.chart), samples), self.chart.config)

    @classmethod
    def from_birth(cls, birth: BirthData, config: ChartConfig | None = None, **kw) -> "Kundli":
        return cls(birth, config or ChartConfig.lahiri(), **kw)

    def dashas(self, depth: int = 3) -> list[DashaPeriod]:
        return vimshottari.periods(self.chart, depth)

    def ayanamsa_sensitivity(self, alternatives=("TRUE_CITRA", "KRISHNAMURTI", "YUKTESHWAR", "RAMAN")
                             ) -> dict[str, list[str]]:
        """Ids of nominal facts whose categorical content differs (or vanishes) under each alternative
        ayanamsa: modelling uncertainty, as the birth window is timing uncertainty."""
        nominal = build_facts(self.chart)
        out = {}
        for alt in alternatives:
            other = {f.id: f for f in build_facts(compute(self.birth, self.config.model_copy(update={"ayanamsa": alt})))}
            out[alt] = [f.id for f in nominal if f.id not in other or fact_key(other[f.id]) != fact_key(f)]
        return out
