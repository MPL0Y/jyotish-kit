from jyotish_kit.config import ChartConfig
from jyotish_kit.ephemeris.engine import compute
from jyotish_kit.models import BirthData, Chart


def window_offsets(birth: BirthData, step_sec: float | None = None) -> list[float]:
    """Second offsets sampling [-u, +u] including both ends and 0.

    Default step gives ~60 samples per window, clamped to 1..30 s.
    """
    half = birth.time_uncertainty_min * 60
    step_sec = step_sec or min(30, max(1, half / 30))
    n = int(half // step_sec)
    offs = [i * step_sec for i in range(-n, n + 1)]
    if half % step_sec:
        offs = [-half, *offs, half]
    return offs


def compute_window(birth: BirthData, cfg: ChartConfig, step_sec: float | None = None) -> list[Chart]:
    return [compute(birth, cfg, o) for o in window_offsets(birth, step_sec)]
