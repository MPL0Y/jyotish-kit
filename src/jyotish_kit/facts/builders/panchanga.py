"""Janma panchanga, avakahada chakra and upagrahas.

Panchanga limbs at the birth moment (not at sunrise, as an almanac would print for the day):
- tithi: Moon - Sun elongation in 12 deg steps; karana: 6 deg steps (Kimstughna, 8 x 7 movable, then
  Shakuni, Chatushpada, Naga); yoga: Sun + Moon in 13 deg 20' steps; vara: weekday of the sunrise that
  began the Vedic day (a pre-dawn birth belongs to the previous weekday).
- lunar month (amanta): named from the sidereal sign the Sun occupies at the new moon that began it,
  plus one (Sun in Pisces -> Chaitra); adhika when the Sun does not change sign before the next new moon.
  Purnimanta months run from full moon, so in krishna paksha they carry the next month's name
  (except an adhika month, which is amanta in both systems).
- ritu from the amanta month (2 months each from Chaitra); ayana from the tropical Sun.
Avakahada (Moon based): varna, vashya, yoni, gana, nadi as used in ashtakoota matching (Muhurta
Chintamani tables).
Upagrahas (P.V.R. Narasimha Rao, *Vedic Astrology: An Integrated Approach* ch.4; JHora settings):
- Sun based: Dhuma = Sun + 133 deg 20'; Vyatipata = 360 - Dhuma; Parivesha = Vyatipata + 180;
  Indrachapa = 360 - Parivesha; Upakethu = Indrachapa + 16 deg 40'.
- Time based: the day (sunrise-sunset) or night (sunset-sunrise) in 8 equal parts, lorded from the
  weekday lord (day) or the 5th lord from it (night) in weekday order, the 8th part lordless. The Lagna
  rising at the middle of the Sun's / Mars' / Mercury's / Jupiter's part is Kala / Mrityu /
  Ardhaprahara / Yamaghantaka; Gulika at the start of Saturn's part and Mandi at its middle (JHora;
  PVR's book has these two the other way round).
"""

from datetime import timedelta

from jyotish_kit.ephemeris.engine import bodies_at, jd_from_utc, lagna_at
from jyotish_kit.facts.builders.nakshatra import NAKSHATRAS, nakshatra, nakshatra_lord
from jyotish_kit.facts.builders.placements import house
from jyotish_kit.models import SEVEN, SIGN_LORDS, SIGNS, Chart, Fact, FactKind

TITHIS = ("Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami",
          "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi")
YOGAS = ("Vishkumbha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma", "Dhriti", "Shula",
         "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyan",
         "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti")
MOVABLE_KARANAS = ("Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti")
MASAS = ("Chaitra", "Vaishakha", "Jyeshtha", "Ashadha", "Shravana", "Bhadrapada", "Ashvina", "Kartika",
         "Margashirsha", "Pausha", "Magha", "Phalguna")
RITUS = ("Vasanta", "Grishma", "Varsha", "Sharad", "Hemanta", "Shishira")
WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

VARNA = ("Kshatriya", "Vaishya", "Shudra", "Brahmin") * 3  # fire, earth, air, water
YONI = ("Horse", "Elephant", "Sheep", "Serpent", "Serpent", "Dog", "Cat", "Sheep", "Cat", "Rat", "Rat", "Cow",
        "Buffalo", "Tiger", "Buffalo", "Tiger", "Deer", "Deer", "Dog", "Monkey", "Mongoose", "Monkey", "Lion",
        "Horse", "Lion", "Cow", "Elephant")
GANA = ("Deva", "Manushya", "Rakshasa", "Manushya", "Deva", "Manushya", "Deva", "Deva", "Rakshasa", "Rakshasa",
        "Manushya", "Manushya", "Deva", "Rakshasa", "Deva", "Rakshasa", "Deva", "Rakshasa", "Rakshasa",
        "Manushya", "Manushya", "Deva", "Rakshasa", "Rakshasa", "Manushya", "Manushya", "Deva")
NADI = ("Adi (Vata)", "Madhya (Pitta)", "Antya (Kapha)")


def vashya(lon: float) -> str:
    sign, deg = int(lon // 30), lon % 30
    if sign == 8:
        return "Manava" if deg < 15 else "Chatushpada"
    if sign == 9:
        return "Chatushpada" if deg < 15 else "Jalachara"
    return ("Chatushpada", "Chatushpada", "Manava", "Jalachara", "Vanachara", "Manava", "Manava", "Keeta",
            None, None, "Manava", "Jalachara")[sign]


def karana(elong: float) -> str:
    k = int(elong // 6)
    if k == 0:
        return "Kimstughna"
    if k >= 57:
        return ("Shakuni", "Chatushpada", "Naga")[k - 57]
    return MOVABLE_KARANAS[(k - 1) % 7]


def _elongation(t, cfg) -> float:
    b = bodies_at(jd_from_utc(t), cfg)
    return (b["Moon"].lon - b["Sun"].lon) % 360


def syzygy(t, cfg, target: float, direction: int):
    """Moment the Moon-Sun elongation equals `target` (0 new moon, 180 full moon), before (-1) or after (+1) t."""
    e = _elongation(t, cfg)
    gap = (target - e) % 360 if direction > 0 else -((e - target) % 360)
    t = t + timedelta(days=gap / 12.19)
    for _ in range(8):
        b = bodies_at(jd_from_utc(t), cfg)
        d = (target - (b["Moon"].lon - b["Sun"].lon) + 180) % 360 - 180
        t += timedelta(days=d / (b["Moon"].speed - b["Sun"].speed))
        if abs(d) < 1e-6:
            break
    return t


def vara_lord(chart: Chart) -> str:
    """Lord of the Vedic weekday: the local date of the sunrise that began the day (Sunday = Sun)."""
    return SEVEN[((chart.sunrise + chart.birth.utc_offset()).weekday() + 1) % 7]


def lunar_month(chart: Chart) -> dict:
    cfg = chart.config
    prev_nm, next_nm = syzygy(chart.utc, cfg, 0, -1), syzygy(chart.utc, cfg, 0, +1)
    s0 = bodies_at(jd_from_utc(prev_nm), cfg)["Sun"].sign
    s1 = bodies_at(jd_from_utc(next_nm), cfg)["Sun"].sign
    amanta = (s0 + 1) % 12
    shukla = (chart.bodies["Moon"].lon - chart.bodies["Sun"].lon) % 360 < 180
    # An adhika month is new moon to new moon in both systems.
    return {"amanta": MASAS[amanta], "purnimanta": MASAS[amanta if shukla or s0 == s1 else (amanta + 1) % 12],
            "adhika": s0 == s1, "ritu": RITUS[amanta // 2], "new_moon_before": prev_nm, "new_moon_after": next_nm}


def panchanga(chart: Chart) -> dict:
    b = chart.bodies
    e = (b["Moon"].lon - b["Sun"].lon) % 360
    t = int(e // 12)
    paksha = "Shukla" if t < 15 else "Krishna"
    tithi = "Purnima" if t == 14 else "Amavasya" if t == 29 else TITHIS[t % 15]
    yoga = int(((b["Sun"].lon + b["Moon"].lon) % 360) // (360 / 27))
    weekday = SEVEN.index(vara_lord(chart))
    tropical_sun = (b["Sun"].lon + chart.ayanamsa) % 360
    n, pada, _ = nakshatra(b["Moon"].lon)
    return {"tithi": tithi, "tithi_number": t + 1, "paksha": paksha, "tithi_elapsed": (e % 12) / 12,
            "vara": WEEKDAYS[weekday], "vara_lord": SEVEN[weekday], "nakshatra": NAKSHATRAS[n], "pada": pada,
            "nakshatra_lord": nakshatra_lord(n), "yoga": YOGAS[yoga], "yoga_number": yoga + 1, "karana": karana(e),
            "ayana": "Uttarayana" if tropical_sun >= 270 or tropical_sun < 90 else "Dakshinayana",
            "day_birth": chart.is_day, **lunar_month(chart)}


def avakahada(chart: Chart) -> dict:
    moon = chart.bodies["Moon"]
    n, pada, _ = nakshatra(moon.lon)
    return {"rashi": SIGNS[moon.sign], "rashi_lord": SIGN_LORDS[moon.sign], "nakshatra": NAKSHATRAS[n], "pada": pada,
            "nakshatra_lord": nakshatra_lord(n), "varna": VARNA[moon.sign], "vashya": vashya(moon.lon),
            "yoni": YONI[n], "gana": GANA[n], "nadi": NADI[(0, 1, 2, 2, 1, 0)[n % 6]]}


def solar_upagrahas(sun: float) -> dict[str, float]:
    dhuma = (sun + 133 + 1 / 3) % 360
    vyatipata = (360 - dhuma) % 360
    parivesha = (vyatipata + 180) % 360
    indrachapa = (360 - parivesha) % 360
    return {"Dhuma": dhuma, "Vyatipata": vyatipata, "Parivesha": parivesha, "Indrachapa": indrachapa,
            "Upaketu": (indrachapa + 16 + 2 / 3) % 360}


TIME_UPAGRAHAS = {"Kala": ("Sun", 0.5), "Mrityu": ("Mars", 0.5), "Ardhaprahara": ("Mercury", 0.5),
                  "Yamaghantaka": ("Jupiter", 0.5), "Gulika": ("Saturn", 0.0), "Mandi": ("Saturn", 0.5)}


def time_upagrahas(chart: Chart) -> dict[str, float]:
    weekday = SEVEN.index(vara_lord(chart))
    start, end = (chart.sunrise, chart.sunset) if chart.is_day else (chart.sunset, chart.next_sunrise)
    first = weekday if chart.is_day else (weekday + 4) % 7
    part = (end - start) / 8
    out = {}
    for name, (lord, frac) in TIME_UPAGRAHAS.items():
        k = (SEVEN.index(lord) - first) % 7
        t = start + part * (k + frac)
        out[name] = lagna_at(jd_from_utc(t), chart.birth.lat, chart.birth.lon, chart.config)
    return out


def upagrahas(chart: Chart) -> dict[str, float]:
    return solar_upagrahas(chart.bodies["Sun"].lon) | time_upagrahas(chart)


def build(chart: Chart) -> list[Fact]:
    facts = [Fact(id="panchanga:birth", kind=FactKind.panchanga, varga="D1", subject="birth", attrs=panchanga(chart)),
             Fact(id="avakahada:birth", kind=FactKind.panchanga, varga="D1", subject="Moon", attrs=avakahada(chart))]
    lagna = chart.bodies["Lagna"].sign
    for name, lon in upagrahas(chart).items():
        n, pada, _ = nakshatra(lon)
        facts.append(Fact(id=f"upagraha:D1:{name}", kind=FactKind.upagraha, subject=name,
                          attrs={"longitude": lon, "sign": SIGNS[int(lon // 30)], "degree": lon % 30,
                                 "house": house(int(lon // 30), lagna), "nakshatra": NAKSHATRAS[n], "pada": pada}))
    return facts
