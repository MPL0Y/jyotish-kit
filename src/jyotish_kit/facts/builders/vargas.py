"""Divisional chart sign mapping: the Shodasavarga per BPHS ch.6 (traditional Parashari method).

Several vargas have competing methods (parivritti, Somanatha, Jagannatha drekkana, Raman hora, ...).
Only the traditional Parashari method is implemented; ChartConfig.varga_method names it explicitly.
"""

VARGAS = ("D1", "D2", "D3", "D4", "D7", "D9", "D10", "D12", "D16", "D20", "D24", "D27", "D30", "D40", "D45", "D60")
ARIES, CANCER, LEO, LIBRA, SAGITTARIUS = 0, 3, 4, 6, 8

# Trimsamsa (D30): (end degree, sign) runs; odd signs and even signs differ.
_D30_ODD = ((5, 0), (10, 10), (18, 8), (25, 2), (30, 6))     # Mars, Saturn, Jupiter, Mercury, Venus
_D30_EVEN = ((5, 1), (12, 5), (20, 11), (25, 9), (30, 7))    # Venus, Mercury, Jupiter, Saturn, Mars


def _by_modality(sign: int, movable: int, fixed: int, dual: int) -> int:
    return (movable, fixed, dual)[sign % 3]


def varga_sign(lon: float, varga: str) -> int:
    """Sign index (0=Aries) of a sidereal longitude in the given divisional chart."""
    lon %= 360
    sign, deg = int(lon // 30), lon % 30
    odd = sign % 2 == 0  # Aries (index 0) is an odd sign
    n = int(varga[1:])
    part = int(deg * n // 30)
    match n:
        case 1:
            return sign
        case 2:  # Hora: odd signs Sun (Leo) then Moon (Cancer); even signs reversed
            return (LEO if part == 0 else CANCER) if odd else (CANCER if part == 0 else LEO)
        case 3:  # Drekkana: sign, 5th, 9th
            return (sign + 4 * part) % 12
        case 4:  # Chaturthamsa: sign, 4th, 7th, 10th
            return (sign + 3 * part) % 12
        case 7:  # Saptamsa: odd from the sign, even from the 7th
            return (sign + (0 if odd else 6) + part) % 12
        case 9 | 27:  # Navamsa / Nakshatramsa: continuous count from Aries
            return int(lon * n // 30) % 12
        case 10:  # Dasamsa: odd from the sign, even from the 9th
            return (sign + (0 if odd else 8) + part) % 12
        case 12 | 60:  # Dwadasamsa / Shashtyamsa: from the sign itself
            return (sign + part) % 12
        case 16 | 45:  # movable from Aries, fixed from Leo, dual from Sagittarius
            return (_by_modality(sign, ARIES, LEO, SAGITTARIUS) + part) % 12
        case 20:  # movable from Aries, fixed from Sagittarius, dual from Leo
            return (_by_modality(sign, ARIES, SAGITTARIUS, LEO) + part) % 12
        case 24:  # Siddhamsa: odd from Leo, even from Cancer
            return ((LEO if odd else CANCER) + part) % 12
        case 30:
            return next(s for end, s in (_D30_ODD if odd else _D30_EVEN) if deg < end)
        case 40:  # Khavedamsa: odd from Aries, even from Libra
            return ((ARIES if odd else LIBRA) + part) % 12
    raise ValueError(f"varga {varga} not implemented")
