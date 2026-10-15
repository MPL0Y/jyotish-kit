NAKSHATRAS = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya",
    "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati")
# Vimshottari order; nakshatra n is ruled by DASHA_ORDER[n % 9].
DASHA_ORDER = ("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury")
SPAN = 360 / 27


def nakshatra(lon: float) -> tuple[int, int, float]:
    """(nakshatra index 0..26, pada 1..4, fraction of the nakshatra elapsed)."""
    lon %= 360
    n = int(lon // SPAN)
    frac = (lon - n * SPAN) / SPAN
    return n, int(frac * 4) + 1, frac


def nakshatra_lord(n: int) -> str:
    return DASHA_ORDER[n % 9]
