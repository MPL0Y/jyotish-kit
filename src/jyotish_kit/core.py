from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jyotish_kit.config import ChartConfig
from jyotish_kit.ephemeris.engine import compute
from jyotish_kit.ephemeris.uncertainty import compute_window, window_offsets
from jyotish_kit.facts.builders.dashas import kalachakra, rasi, vimshottari, yogini
from jyotish_kit.facts.graph import FactGraph, build_facts, fact_key, merge_window
from jyotish_kit.facts.transits import transit_facts, sade_sati_periods
from jyotish_kit.models import BirthData, Chart, DashaPeriod, SIGNS, PLANETS, SEVEN
from jyotish_kit.report import report as render_report
from jyotish_kit.synthesis import Synthesis
from jyotish_kit.timing import windows as timing_windows


class Kundli:
    """Base Kundli calculation class maintaining backwards compatibility."""

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

    def ayanamsa_sensitivity(
        self, alternatives=("TRUE_CITRA", "KRISHNAMURTI", "YUKTESHWAR", "RAMAN")
    ) -> dict[str, list[str]]:
        nominal = build_facts(self.chart)
        out = {}
        for alt in alternatives:
            other = {
                f.id: f
                for f in build_facts(
                    compute(self.birth, self.config.model_copy(update={"ayanamsa": alt}))
                )
            }
            out[alt] = [
                f.id for f in nominal if f.id not in other or fact_key(other[f.id]) != fact_key(f)
            ]
        return out


class Jyotish(Kundli):
    """
    High-level, developer-friendly interface to the Jyotish Knowledge Engine.
    Provides intuitive methods to compute planetary states, divisional charts,
    dashas, transits, Ashtakavarga, timing windows, and LLM ground-truth payloads.
    """

    @classmethod
    def create(
        cls,
        dt_local: datetime | str,
        lat: float,
        lon: float,
        tz_name: str = "Asia/Kolkata",
        place_name: str | None = None,
        time_uncertainty_min: float = 0.5,
        ayanamsa: str = "LAHIRI",
    ) -> "Jyotish":
        """Convenient constructor accepting scalar parameters."""
        if isinstance(dt_local, str):
            dt_local = datetime.fromisoformat(dt_local)
        if dt_local.tzinfo is not None:
            dt_local = dt_local.replace(tzinfo=None)

        birth = BirthData(
            dt_local=dt_local,
            lat=lat,
            lon=lon,
            tz_name=tz_name,
            place_name=place_name or "",
            time_uncertainty_min=time_uncertainty_min,
        )
        cfg = ChartConfig(ayanamsa=ayanamsa)
        return cls(birth=birth, config=cfg)

    def get_panchanga(self) -> dict[str, Any]:
        """Returns the 5 sacred limbs of Panchanga for the birth moment."""
        p_facts = {f.subject: f.attrs for f in self.facts.query("panchanga")}
        return {
            "vara": p_facts.get("vara", {}),
            "tithi": p_facts.get("tithi", {}),
            "nakshatra": p_facts.get("nakshatra", {}),
            "yoga": p_facts.get("yoga", {}),
            "karana": p_facts.get("karana", {}),
            "sunrise": self.chart.sunrise.isoformat(),
            "sunset": self.chart.sunset.isoformat(),
            "is_day": self.chart.is_day,
        }

    def get_planets(self) -> dict[str, Any]:
        """Returns detailed planetary states including signs, degrees, dignities, and avasthas."""
        res = {}
        for name, body in self.chart.bodies.items():
            p = self.facts.get(f"placement:D1:{name}")
            d9 = self.facts.get(f"placement:D9:{name}")
            d10 = self.facts.get(f"placement:D10:{name}")
            dignity = self.facts.get(f"dignity:D1:{name}")
            chalit = self.facts.get(f"chalit:{name}")
            avastha_baladi = self.facts.get(f"avastha:baladi:{name}")

            res[name] = {
                "sign": p.attrs.get("sign") if p else SIGNS[body.sign],
                "degree": round(body.deg, 4),
                "is_retrograde": body.retro,
                "nakshatra": p.attrs.get("nakshatra") if p else None,
                "pada": p.attrs.get("pada") if p else None,
                "house": p.attrs.get("house") if p else None,
                "chalit_house": chalit.attrs.get("house") if chalit else None,
                "dignity": dignity.attrs.get("status") if dignity else None,
                "baladi_avastha": avastha_baladi.attrs.get("avastha") if avastha_baladi else None,
                "d9_sign": d9.attrs.get("sign") if d9 else None,
                "d10_sign": d10.attrs.get("sign") if d10 else None,
            }
        return res

    def get_vargas(self, vargas: list[str] | None = None) -> dict[str, dict[str, str]]:
        """Returns divisional chart placements (D1 to D60)."""
        target = vargas or [
            "D1", "D2", "D3", "D4", "D7", "D9", "D10", "D12",
            "D16", "D20", "D24", "D27", "D30", "D40", "D45", "D60"
        ]
        out = {}
        for v in target:
            out[v] = {}
            for name in list(self.chart.bodies.keys()):
                f = self.facts.get(f"placement:{v}:{name}")
                if f:
                    out[v][name] = f.attrs.get("sign")
        return out

    def get_bhavas(self) -> dict[str, Any]:
        """Returns whole sign, Bhava Chalit (Sripati), and KP cusps."""
        whole_sign = {}
        for h in range(1, 13):
            lord_fact = self.facts.get(f"lordship:D1:H{h}")
            occupants = [
                name for name in self.chart.bodies.keys()
                if self.facts.get(f"placement:D1:{name}")
                and self.facts.get(f"placement:D1:{name}").attrs.get("house") == h
            ]
            sav_fact = self.facts.get(f"ashtakavarga:SAV:{h}")
            whole_sign[f"House_{h}"] = {
                "sign": lord_fact.attrs.get("sign") if lord_fact else None,
                "lord": lord_fact.attrs.get("lord") if lord_fact else None,
                "occupants": occupants,
                "sav_bindus": sav_fact.attrs.get("bindus") if sav_fact else None,
            }

        chalit = {}
        for name in self.chart.bodies.keys():
            c = self.facts.get(f"chalit:{name}")
            if c:
                chalit[name] = c.attrs.get("house")

        kp_cusps = {}
        for h in range(1, 13):
            c_fact = self.facts.get(f"kp_lords:KP:C{h}")
            if c_fact:
                kp_cusps[f"Cusp_{h}"] = c_fact.attrs

        return {
            "whole_sign": whole_sign,
            "bhava_chalit_placements": chalit,
            "kp_cusps": kp_cusps,
        }

    def get_ashtakavarga(self) -> dict[str, Any]:
        """Returns Sarvashtakavarga (SAV) and Bhinnashtakavarga (BAV) bindu distributions."""
        sav_by_sign = {}
        for s in SIGNS:
            f = self.facts.get(f"ashtakavarga:SAV:{s}")
            if f:
                sav_by_sign[s] = f.attrs.get("bindus")

        lagna_sign_idx = self.chart.bodies["Lagna"].sign
        sav_by_house = {}
        for h in range(1, 13):
            sign = SIGNS[(lagna_sign_idx + h - 1) % 12]
            sav_by_house[h] = sav_by_sign.get(sign)

        bav = {}
        for planet in SEVEN:
            bav[planet] = {}
            for s in SIGNS:
                f = self.facts.get(f"ashtakavarga:BAV:{planet}:{s}")
                if f:
                    bav[planet][s] = f.attrs.get("bindus")

        return {"SAV": sav_by_house, "SAV_by_sign": sav_by_sign, "BAV": bav}

    def get_shadbala(self) -> dict[str, Any]:
        """Returns Shadbala strengths in Rupas and strength multipliers."""
        res = {}
        for planet in SEVEN:
            f = self.facts.get(f"shadbala:{planet}")
            if f:
                res[planet] = {
                    "rupas": round(f.attrs.get("rupas", 0), 2),
                    "ratio": round(f.attrs.get("ratio", 0), 2),
                    "is_strong": f.attrs.get("ratio", 0) >= 1.0,
                }
        return res

    def get_dashas(self, system: str = "vimshottari", depth: int = 2) -> list[dict[str, Any]]:
        """Returns active and upcoming dasha periods for the specified system."""
        sys = system.lower()
        if sys == "vimshottari":
            periods = vimshottari.periods(self.chart, depth=depth)
        elif sys == "yogini":
            periods = yogini.periods(self.chart, depth=depth)
        elif sys == "kalachakra":
            periods = kalachakra.periods(self.chart, depth=depth)
        elif sys == "chara":
            periods = rasi.chara_periods(self.chart, depth=depth)
        elif sys == "narayana":
            periods = rasi.narayana_periods(self.chart, depth=depth)
        else:
            raise ValueError(f"Unsupported dasha system: {system}")

        out = []
        for p in periods:
            out.append({
                "lords": list(p.lords),
                "level": len(p.lords),
                "start": p.start.isoformat(),
                "end": p.end.isoformat(),
                "system": system,
            })
        return out

    def get_transits(self, transit_dt: datetime | None = None) -> dict[str, Any]:
        """Calculates transits (Gochara) against the natal chart for any given moment."""
        t_time = transit_dt or datetime.now(ZoneInfo(self.birth.tz_name))
        t_facts = transit_facts(self.chart, t_time)
        sade_sati = sade_sati_periods(self.chart, t_time.year, t_time.year + 15)

        transits = {}
        for f in t_facts:
            transits[f.subject] = f.attrs

        return {
            "transit_time": t_time.isoformat(),
            "positions": transits,
            "sade_sati_upcoming": [
                {
                    "phase": p.kind.replace("sade_sati:", ""),
                    "start": p.attrs["start"].strftime("%Y-%m"),
                    "end": p.attrs["end"].strftime("%Y-%m"),
                }
                for p in sade_sati
            ],
        }

    def get_timing(
        self,
        topic: str = "career",
        years: int = 5,
        start_dt: datetime | None = None,
        drafts: bool = True,
        school: str = "parashari",
    ) -> list[dict[str, Any]]:
        """Computes top timing windows for a specific life domain using multi-school synthesis."""
        tz = ZoneInfo(self.birth.tz_name)
        start = start_dt or datetime.now(tz)
        if start.tzinfo is None:
            start = start.replace(tzinfo=tz)
        end = start + timedelta(days=years * 365.25)
        syn = Synthesis(self, include_drafts=drafts)
        res = timing_windows(syn, topic, school, start, end)
        out = []
        for w in res.windows:
            out.append({
                "school": res.school,
                "start": w.start.isoformat(),
                "end": w.end.isoformat(),
                "score": round(w.score, 2),
                "lords": w.lords,
                "drivers": w.drivers,
            })
        return out

    def to_llm_context(self, topics: list[str] | None = None) -> dict[str, Any]:
        """
        Builds a deterministic ground-truth JSON payload containing verified
        astrometric facts, planetary dignities, running dashas, and cited rule
        evidence. Inject this into LLM system prompts to prevent hallucinations.
        """
        target_topics = topics or ["career", "wealth", "fortune", "spirituality"]
        syn = Synthesis(self, include_drafts=True)
        judgments = {}
        for t in target_topics:
            judgments[t] = [syn.judge(t, s).model_dump() for s in syn.schools]

        return {
            "subject": {
                "place_name": self.birth.place_name,
                "birth_local": self.birth.dt_local.isoformat(),
                "ayanamsa": self.config.ayanamsa,
            },
            "planets": self.get_planets(),
            "ashtakavarga": self.get_ashtakavarga(),
            "shadbala": self.get_shadbala(),
            "panchanga": self.get_panchanga(),
            "judgments": judgments,
            "disclaimer": "Ground-truth mathematical facts computed via Swiss Ephemeris. Do not alter dates or signs.",
        }

    def generate_report(self, out_path: Path | str | None = None) -> str:
        """Generates the full comprehensive Markdown Kundli dossier."""
        md = render_report(self)
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(md, encoding="utf-8")
        return md
