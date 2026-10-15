"""Explicit chart conventions. Every place classical authorities differ is a field here.

Nothing downstream may assume a convention that is not read from ChartConfig.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# (sign_index 0=Aries, start_deg, end_deg). BPHS ch.3 (Graha Guna Svarupa).
# Moon's Taurus range is disputed: BPHS gives 3–30 (after the 3° exaltation point);
# some later texts give 4–30 or 4–20. Override per-planet if you follow another text.
DEFAULT_MOOLATRIKONA: dict[str, tuple[int, float, float]] = {
    "Sun": (4, 0, 20),
    "Moon": (1, 3, 30),
    "Mars": (0, 0, 12),
    "Mercury": (5, 15, 20),
    "Jupiter": (8, 0, 10),
    "Venus": (6, 0, 15),
    "Saturn": (10, 0, 20),
    "Rahu": (2, 0, 30),   # BPHS ch.3; whole sign
    "Ketu": (8, 0, 30),
}

# Combustion orbs in degrees from the Sun, Surya Siddhanta ch.9 (verse numbers to be pinned when the corpus lands).
# Mercury and Venus have reduced orbs when retrograde.
DEFAULT_COMBUSTION = {"Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11, "Venus": 10, "Saturn": 15}
DEFAULT_COMBUSTION_RETRO = {"Mercury": 12, "Venus": 8}


class ChartConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Swiss Ephemeris sidereal mode name: swe.SIDM_<ayanamsa>.
    ayanamsa: str = "LAHIRI"
    node: Literal["true", "mean"] = "true"
    # Parashari bhava = whole sign. Placidus cusps are always computed too (for KP).
    house_system: Literal["whole_sign", "placidus"] = "whole_sign"
    # Dasha year length in days. Default: mean sidereal year (Sun's return to the same sidereal
    # point; JHora's default). Alternatives: 365.2425 Gregorian, 365.25 Julian, 360 savana.
    dasha_year_days: float = 365.256363
    # Graha drishti for the nodes, counted as houses from the node.
    # Classical views: () none; (5, 7, 9) like Jupiter (widely used Parashari practice);
    # (5, 7, 9, 12); (2, 5, 7, 9, 12). Undecided between them -> see README "Open conventions".
    rahu_aspects: tuple[int, ...] = (5, 7, 9)
    ketu_aspects: tuple[int, ...] = (5, 7, 9)
    # Node exaltation is disputed (Rahu: Taurus or Gemini; Ketu: Scorpio or Sagittarius).
    # Default BPHS ch.3: Rahu exalted Taurus / MT Gemini, Ketu exalted Scorpio / MT Sagittarius.
    # Map of node -> exaltation sign index. Empty = nodes get no dignity.
    node_exaltation: dict[str, int] = {"Rahu": 1, "Ketu": 7}
    moolatrikona: dict[str, tuple[int, float, float]] = DEFAULT_MOOLATRIKONA
    combustion_orbs: dict[str, float] = DEFAULT_COMBUSTION
    combustion_orbs_retro: dict[str, float] = DEFAULT_COMBUSTION_RETRO
    # Graha yuddha: planets (Mars..Saturn) within this many degrees of longitude.
    war_orb: float = 1.0
    # Winner: Surya Siddhanta ch.7 — the planet with the northern (greater) latitude;
    # alternative: the brighter (lower visual magnitude) planet.
    war_winner: Literal["north_latitude", "brightness"] = "north_latitude"
    # Sunrise: "hindu" = centre of disc, no refraction (Surya Siddhanta convention, JHora default);
    # "limb" = upper limb with refraction (modern almanacs).
    sunrise: Literal["limb", "hindu"] = "hindu"
    # Jaimini chara karakas: 8 (Sun..Saturn + Rahu, Rahu's degree counted from sign end; BPHS ch.32,
    # JHora default) or 7 (Sun..Saturn).
    chara_karakas: Literal[7, 8] = 8
    # Lords of Scorpio/Aquarius in Jaimini calculations (arudhas, dashas): "stronger" of Mars/Ketu and
    # Saturn/Rahu by the Jaimini co-lord rules, or "parashari" = Mars / Saturn only.
    co_lords: Literal["stronger", "parashari"] = "stronger"
    # Node exaltation signs for Jaimini rules (co-lord strength, sign dasha years): JHora uses
    # Rahu Ta+Ge / Ketu Sc+Sg; debilitation is the opposite sign. Parashari dignity uses node_exaltation.
    jaimini_node_exaltation: dict[str, tuple[int, ...]] = {"Rahu": (1, 2), "Ketu": (7, 8)}
    # Ishta kala for Bhava/Hora/Ghati lagna: measured from the sunrise that began the Vedic day
    # ("vedic_day", classical; a pre-dawn birth uses the previous sunrise) or from the sunrise of the
    # civil date ("civil_date", PyJHora). Differs by about the Sun's daily motion (~1°) for pre-dawn births.
    special_lagna_sunrise: Literal["vedic_day", "civil_date"] = "vedic_day"
    # Ekadhipatya shodhana when one sign of a pair is occupied and the empty one has more bindus:
    # "bphs" = subtract the occupied count (BPHS 68.1-5); "equalize" = make it equal (Raman, PyJHora).
    ekadhipatya_mode: Literal["bphs", "equalize"] = "bphs"
    # KP positions/cusps use their own ayanamsa (KP practice: Krishnamurti, ~6' from Lahiri).
    kp_ayanamsa: str = "KRISHNAMURTI"
    # Pushkara bhaga degree per sign: "jataka_parijata" (21 14 18 8 19 9 24 11 23 14 19 9) or "element"
    # (21 14 24 7 repeating by element; PyJHora's default, source unnamed).
    pushkara_bhaga: Literal["jataka_parijata", "element"] = "jataka_parijata"
    include_outer: bool = False

    @classmethod
    def lahiri(cls, **kw) -> "ChartConfig":
        return cls(ayanamsa="LAHIRI", **kw)
