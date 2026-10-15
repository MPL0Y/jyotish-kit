"""Ashtakavarga (BPHS ch.66–68): BAV per planet, SAV, trikona and ekadhipatya shodhana.

Tables are transcribed house-major exactly as BPHS 66.43–60 states them ("in the AV of X:
A, B in the 1st ...") so they can be checked against the verse. One edition note: the
Sharma edition (vedpuran.net PDF) deviates from the standard tables (B.V. Raman, JHora/PyJHora) twice;
we follow the standard reading in both, totals are unaffected except where noted:
  - Guru's AV omits Guru from the 1st and 4th (total 54 instead of 56) -> included.
  - Budh's AV lists Sani in the 5th where the standard lists Surya -> Surya.
"""

from jyotish_kit.facts.builders.placements import signs
from jyotish_kit.models import SEVEN, SIGN_LORDS, SIGNS, Chart, Fact, FactKind

_ALL = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna")


def _except(*xs):
    return tuple(c for c in _ALL if c not in xs)


# planet -> house counted from contributor -> contributors giving a rekha (bindu)
BAV_TABLE: dict[str, dict[int, tuple[str, ...]]] = {
    "Sun": {  # BPHS 66.43-45
        1: ("Saturn", "Mars", "Sun"), 2: ("Saturn", "Mars", "Sun"), 8: ("Saturn", "Mars", "Sun"),
        5: ("Jupiter", "Mercury"), 3: ("Mercury", "Moon", "Lagna"), 4: ("Lagna", "Sun", "Saturn", "Mars"),
        10: ("Lagna", "Sun", "Saturn", "Mars", "Mercury", "Moon"), 11: _except("Venus"),
        12: ("Lagna", "Venus", "Mercury"), 6: ("Lagna", "Venus", "Mercury", "Jupiter", "Moon"),
        7: ("Sun", "Mars", "Saturn", "Venus"), 9: ("Sun", "Mars", "Saturn", "Mercury", "Jupiter")},
    "Moon": {  # BPHS 66.46-48
        1: ("Mercury", "Moon", "Jupiter"), 2: ("Jupiter", "Mars"),
        3: ("Mercury", "Sun", "Moon", "Mars", "Saturn", "Venus", "Lagna"), 4: ("Jupiter", "Venus", "Mercury"),
        5: ("Mars", "Mercury", "Venus", "Saturn"), 6: ("Sun", "Moon", "Mars", "Saturn", "Lagna"),
        7: ("Sun", "Moon", "Jupiter", "Mercury", "Venus"), 8: ("Sun", "Mercury", "Jupiter"), 9: ("Venus", "Moon"),
        10: ("Sun", "Mercury", "Jupiter", "Venus", "Moon", "Lagna", "Mars"), 11: _ALL, 12: ()},
    "Mars": {  # BPHS 66.49-50
        1: ("Lagna", "Saturn", "Mars"), 2: ("Mars",), 3: ("Lagna", "Mercury", "Moon", "Sun"),
        4: ("Saturn", "Mars"), 5: ("Mercury", "Sun"), 6: ("Mercury", "Moon", "Jupiter", "Sun", "Lagna", "Venus"),
        7: ("Saturn", "Mars"), 8: ("Saturn", "Mars", "Venus"), 9: ("Saturn",),
        10: ("Mars", "Sun", "Jupiter", "Saturn", "Lagna"), 11: _ALL, 12: ("Jupiter", "Venus")},
    "Mercury": {  # BPHS 66.51-52 (Sun, not Saturn, in the 5th; see module doc)
        1: ("Lagna", "Saturn", "Mars", "Venus", "Mercury"), 2: ("Lagna", "Mars", "Moon", "Venus", "Saturn"),
        3: ("Venus", "Mercury"), 4: ("Lagna", "Moon", "Saturn", "Venus", "Mars"), 5: ("Mercury", "Sun", "Venus"),
        6: ("Jupiter", "Mercury", "Sun", "Moon", "Lagna"), 7: ("Mars", "Saturn"),
        8: ("Mars", "Saturn", "Lagna", "Moon", "Venus", "Jupiter"), 9: ("Saturn", "Mars", "Sun", "Mercury", "Venus"),
        10: ("Lagna", "Saturn", "Mars", "Mercury", "Moon"), 11: _ALL, 12: ("Jupiter", "Mercury", "Sun")},
    "Jupiter": {  # BPHS 66.53-55 (+ Jupiter in 1st/4th, see module doc)
        1: ("Lagna", "Mars", "Sun", "Mercury", "Jupiter"), 4: ("Lagna", "Mars", "Sun", "Mercury", "Jupiter"),
        2: ("Jupiter", "Lagna", "Mars", "Sun", "Mercury", "Moon", "Venus"), 3: ("Saturn", "Jupiter", "Sun"),
        5: ("Venus", "Moon", "Lagna", "Mercury", "Saturn"), 6: ("Venus", "Lagna", "Mercury", "Saturn"),
        7: ("Lagna", "Mars", "Jupiter", "Sun", "Moon"), 8: ("Jupiter", "Sun", "Mars"),
        9: ("Venus", "Sun", "Lagna", "Moon", "Mercury"), 10: ("Jupiter", "Mercury", "Mars", "Sun", "Venus", "Lagna"),
        11: _except("Saturn"), 12: ("Saturn",)},
    "Venus": {  # BPHS 66.56-58
        1: ("Lagna", "Venus", "Moon"), 2: ("Lagna", "Venus", "Moon"),
        3: ("Lagna", "Venus", "Moon", "Mercury", "Saturn", "Mars"), 4: ("Lagna", "Venus", "Moon", "Saturn", "Mars"),
        5: ("Lagna", "Mercury", "Moon", "Jupiter", "Saturn", "Venus"), 6: ("Mercury", "Mars"), 7: (),
        8: ("Venus", "Sun", "Moon", "Jupiter", "Lagna", "Saturn"), 9: _except("Sun"),
        10: ("Venus", "Jupiter", "Saturn"), 11: _ALL, 12: ("Mars", "Moon", "Sun")},
    "Saturn": {  # BPHS 66.59-60
        1: ("Sun", "Lagna"), 2: ("Sun",), 3: ("Lagna", "Moon", "Mars", "Saturn"), 4: ("Lagna", "Sun"),
        5: ("Jupiter", "Saturn", "Mars"), 6: _except("Sun"), 7: ("Sun",), 8: ("Sun", "Mercury"), 9: ("Mercury",),
        10: ("Sun", "Mars", "Lagna", "Mercury"), 11: _ALL, 12: ("Mars", "Mercury", "Jupiter", "Venus")},
}


def bav(chart: Chart) -> dict[str, list[int]]:
    """planet -> 12 bindu counts indexed by sign (0=Aries)."""
    s = signs(chart, "D1")
    out = {}
    for p, table in BAV_TABLE.items():
        row = [0] * 12
        for house, contributors in table.items():
            for c in contributors:
                row[(s[c] + house - 1) % 12] += 1
        out[p] = row
    return out


def trikona_shodhana(row: list[int]) -> list[int]:
    """BPHS 67.3-5: per trine group, no change if any is 0; all equal -> 0; else subtract the minimum."""
    row = row[:]
    for r in range(4):
        g = (r, r + 4, r + 8)
        vals = [row[i] for i in g]
        if 0 in vals:
            continue
        m = 0 if len(set(vals)) == 1 else min(vals)
        for i in g:
            row[i] = 0 if m == 0 else row[i] - m
    return row


def ekadhipatya_shodhana(row: list[int], occupied: set[int], mode: str) -> list[int]:
    """BPHS 68.1-5 for the two signs of Mars, Mercury, Jupiter, Venus, Saturn.

    mode="bphs": occupied smaller & empty bigger -> empty -= occupied (as BPHS 68 states).
    mode="equalize": empty bigger -> made equal to occupied (Raman / PyJHora reading).
    `occupied` = signs holding any of the seven planets (nodes and Lagna do not count).
    """
    row = row[:]
    for lord in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        a, b = (i for i in range(12) if SIGN_LORDS[i] == lord)
        if row[a] == 0 or row[b] == 0 or (a in occupied and b in occupied):
            continue
        if a not in occupied and b not in occupied:
            row[a] = row[b] = 0 if row[a] == row[b] else min(row[a], row[b])
            continue
        occ, emp = (a, b) if a in occupied else (b, a)
        if mode == "bphs":  # bigger empty sign loses the occupied sign's count; otherwise cleared
            row[emp] = row[emp] - row[occ] if row[emp] > row[occ] else 0
        else:
            row[emp] = row[occ] if row[emp] >= row[occ] else 0
    return row


def build(chart: Chart) -> list[Fact]:
    s = signs(chart, "D1")
    occupied = {s[p] for p in SEVEN}
    mode = chart.config.ekadhipatya_mode
    rows = bav(chart)
    facts = []
    for p, row in rows.items():
        tri = trikona_shodhana(row)
        eka = ekadhipatya_shodhana(tri, occupied, mode)
        for i in range(12):
            facts.append(Fact(id=f"ashtakavarga:BAV:{p}:{SIGNS[i]}", kind=FactKind.ashtakavarga, subject=p,
                              object=SIGNS[i], attrs={"bindus": row[i], "after_trikona": tri[i],
                                                      "after_ekadhipatya": eka[i]}))
    for i in range(12):
        facts.append(Fact(id=f"ashtakavarga:SAV:{SIGNS[i]}", kind=FactKind.ashtakavarga, subject="SAV",
                          object=SIGNS[i], attrs={"bindus": sum(r[i] for r in rows.values())}))
    return facts
