"""Shadbala (BPHS ch.27) and Bhava bala, in virupas (60 virupas = 1 rupa).

Conventions follow B.V. Raman, "Graha and Bhava Balas", where BPHS leaves room:
  - Uchcha: distance from the debilitation point / 3.
  - Saptavargaja over D1 D2 D3 D7 D9 D12 D30; moolatrikona (45) only in D1 within its degree range;
    otherwise own 30, compound great friend 22.5, friend 15, neutral 7.5, enemy 3.75, great enemy 1.875.
  - Paksha: benefics elongation/3, malefics 60 - that; the Moon's value is doubled.
  - Ayana: (24 +/- declination) * 1.25, the Sun's doubled. Sun's cheshta = its ayana bala,
    Moon's cheshta = its paksha bala.
  - Abda/masa: weekday lord of the 360/30-day period of the Kali ahargana (epoch Friday, JD 588465.5).
  - Hora: 1-hour horas from sunrise, Chaldean order from the day lord.
  - Drik: Raman's piecewise drishti in virupas with special aspects; (benefic - malefic) / 4.
Cheshta for Mars..Saturn uses the sighra kendra from the true heliocentric longitude
(|helio planet - Sun| folded to 0..180, / 3), the modern form of the Surya Siddhanta mean-motion rule.
"""

from datetime import date, timedelta

from jyotish_kit.facts.builders.dignity import EXALTATION, OWN, relationships
from jyotish_kit.facts.builders.placements import signs
from jyotish_kit.facts.builders.vargas import varga_sign
from jyotish_kit.models import SEVEN, SIGN_LORDS, Chart, Fact, FactKind

SAPTAVARGA = ("D1", "D2", "D3", "D7", "D9", "D12", "D30")
REL_POINTS = {2: 22.5, 1: 15, 0: 7.5, -1: 3.75, -2: 1.875}
NAISARGIKA = {p: round(60 * k / 7, 2) for p, k in zip(
    ("Sun", "Moon", "Venus", "Jupiter", "Mercury", "Mars", "Saturn"), range(7, 0, -1))}
REQUIRED_RUPAS = {"Sun": 6.5, "Moon": 6, "Mars": 5, "Mercury": 7, "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5}
CHALDEAN = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")
WEEKDAY = SEVEN  # Sunday=0 .. Saturday=6
KALI_EPOCH_JD = 588465.5  # Kali yuga epoch, a Friday
MALE, FEMALE = ("Sun", "Mars", "Jupiter"), ("Moon", "Venus")
NATURAL_MALEFICS = ("Sun", "Mars", "Saturn", "Rahu", "Ketu")


def _fold(a: float) -> float:
    a %= 360
    return 360 - a if a > 180 else a


def drishti(angle: float, p: str) -> float:
    """Virupas of p's aspect on a point `angle` degrees ahead of it (Raman's table)."""
    a = angle % 360
    if a < 30 or a >= 300:
        return 0.0
    if a < 60:
        v = (a - 30) / 2
    elif a < 90:
        v = a - 45 + (45 if p == "Saturn" else 0)
    elif a < 120:
        v = (120 - a) / 2 + 30 + (15 if p == "Mars" else 0)
    elif a < 150:
        v = 150 - a + (30 if p == "Jupiter" else 0)
    elif a < 180:
        v = 2 * (a - 150)
    else:
        v = (300 - a) / 2
        v += {"Mars": 15 * (210 <= a < 240), "Jupiter": 30 * (240 <= a < 270),
              "Saturn": 45 * (270 <= a < 300)}.get(p, 0)
    return v


def benefics(chart: Chart) -> set[str]:
    """Jupiter, Venus; waxing Moon; Mercury unless sharing a sign with a natural malefic (BPHS 3.12)."""
    s = signs(chart, "D1")
    b = {"Jupiter", "Venus"}
    if (chart.bodies["Moon"].lon - chart.bodies["Sun"].lon) % 360 < 180:
        b.add("Moon")
    if not any(s[m] == s["Mercury"] for m in NATURAL_MALEFICS):
        b.add("Mercury")
    return b


def sthana(chart: Chart) -> dict[str, dict[str, float]]:
    b, rel, cfg = chart.bodies, relationships(chart), chart.config
    lagna = b["Lagna"].sign
    out = {}
    for p in SEVEN:
        lon, sign = b[p].lon, b[p].sign
        ex = EXALTATION[p][0] * 30 + EXALTATION[p][1]
        uchcha = _fold(lon - ex - 180) / 3
        sv = 0.0
        for v in SAPTAVARGA:
            vs = varga_sign(lon, v)
            mt = cfg.moolatrikona[p]
            if v == "D1" and vs == mt[0] and mt[1] <= b[p].deg < mt[2]:
                sv += 45
            elif vs in OWN[p]:
                sv += 30
            else:
                sv += REL_POINTS[rel[p, SIGN_LORDS[vs]][2]]
        even_lover = p in FEMALE
        oja = sum(15 for x in (sign, varga_sign(lon, "D9")) if (x % 2 == 1) == even_lover)
        kendradi = {0: 60, 1: 30, 2: 15}[((sign - lagna) % 12) % 3]
        dk = int(b[p].deg // 10)
        drekkana = 15.0 if dk == (0 if p in MALE else 2 if p in FEMALE else 1) else 0.0
        out[p] = {"uchcha": uchcha, "saptavargaja": sv, "ojayugma": float(oja), "kendradi": float(kendradi),
                  "drekkana": drekkana}
    return out


def dig(chart: Chart) -> dict[str, float]:
    asc, mc = chart.placidus_cusps[0], chart.placidus_cusps[9]
    weak = {"Sun": mc + 180, "Mars": mc + 180, "Jupiter": asc + 180, "Mercury": asc + 180,
            "Moon": mc, "Venus": mc, "Saturn": asc}  # point of zero dig bala
    return {p: _fold(chart.bodies[p].lon - weak[p]) / 3 for p in SEVEN}


def _ahargana(d: date) -> int:
    return int(d.toordinal() + 1721424.5 - KALI_EPOCH_JD)  # JD of the date's midnight minus the epoch


def kala(chart: Chart, ben: set[str]) -> dict[str, dict[str, float]]:
    from zoneinfo import ZoneInfo
    b, t = chart.bodies, chart.utc
    hours = lambda x: x / timedelta(hours=1)  # noqa: E731
    noon = chart.sunrise + (chart.sunset - chart.sunrise) / 2
    d_noon = abs(hours(t - noon)) % 24
    d_noon = min(d_noon, 24 - d_noon)
    diurnal = 60 * (12 - d_noon) / 12

    elong = _fold(b["Moon"].lon - b["Sun"].lon) / 3

    if t < chart.sunset:
        part = int(3 * (t - chart.sunrise) / (chart.sunset - chart.sunrise))
        tri_lord = ("Mercury", "Sun", "Saturn")[part]
    else:
        part = int(3 * (t - chart.sunset) / (chart.next_sunrise - chart.sunset))
        tri_lord = ("Moon", "Venus", "Mars")[part]

    vedic_date = chart.sunrise.astimezone(ZoneInfo(chart.birth.tz_name)).date()
    ah = _ahargana(vedic_date)
    abda = WEEKDAY[(5 + 3 * (ah // 360)) % 7]
    masa = WEEKDAY[(5 + 2 * (ah // 30)) % 7]
    vara = WEEKDAY[(5 + ah) % 7]
    hora = CHALDEAN[(CHALDEAN.index(vara) + int(hours(t - chart.sunrise))) % 7]

    out = {}
    for p in SEVEN:
        dec = b[p].decl
        signed = abs(dec) if p == "Mercury" else (-dec if p in ("Moon", "Saturn") else dec)
        ayana = (24 + signed) * 1.25 * (2 if p == "Sun" else 1)
        paksha = (elong if p in ben or p == "Moon" else 60 - elong) * (2 if p == "Moon" else 1)
        out[p] = {
            "nathonnatha": 60.0 if p == "Mercury" else diurnal if p in ("Sun", "Jupiter", "Venus") else 60 - diurnal,
            "paksha": paksha,
            "tribhaga": 60.0 if p in ("Jupiter", tri_lord) else 0.0,
            "abda": 15.0 * (p == abda), "masa": 30.0 * (p == masa), "vara": 45.0 * (p == vara),
            "hora": 60.0 * (p == hora), "ayana": ayana,
        }
    return out


def cheshta(chart: Chart, kl: dict) -> dict[str, float]:
    b = chart.bodies
    out = {"Sun": kl["Sun"]["ayana"], "Moon": kl["Moon"]["paksha"]}
    for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        out[p] = _fold(b[p].helio_lon - b["Sun"].lon) / 3
    return out


def shadbala(chart: Chart) -> dict[str, dict[str, float]]:
    ben = benefics(chart)
    st, dg, kl = sthana(chart), dig(chart), kala(chart, ben)
    ch = cheshta(chart, kl)
    out = {}
    for p in SEVEN:
        row = {"sthana": sum(st[p].values()), "dig": dg[p], "kala": sum(kl[p].values()), "cheshta": ch[p],
               "naisargika": NAISARGIKA[p],
               "drik": sum((1 if q in ben else -1) * drishti(chart.bodies[p].lon - chart.bodies[q].lon, q)
                           for q in SEVEN if q != p) / 4}
        out[p] = row | {f"sthana.{k}": v for k, v in st[p].items()} | {f"kala.{k}": v for k, v in kl[p].items()}
    for f in _wars(chart):  # ponytail: yuddha = difference of the pre-war totals, BPHS 27.29; no disc-size division
        w, l = f["winner"], f["loser"]
        diff = sum(out[w][k] for k in ("sthana", "dig", "kala")) - sum(out[l][k] for k in ("sthana", "dig", "kala"))
        for p, sgn in ((w, 1), (l, -1)):
            out[p]["kala.yuddha"] = sgn * abs(diff)
            out[p]["kala"] += sgn * abs(diff)
    for p, row in out.items():
        total = sum(row[k] for k in ("sthana", "dig", "kala", "cheshta", "naisargika", "drik"))
        row |= {"total": total, "rupas": total / 60, "ratio": total / 60 / REQUIRED_RUPAS[p]}
        # Ishta / kashta phala (BPHS 27.37-38): geometric means of uchcha and cheshta bala, or of their complements.
        u, c = row["sthana.uchcha"], row["cheshta"]
        row |= {"ishta_phala": (u * c) ** 0.5, "kashta_phala": ((60 - u) * (60 - c)) ** 0.5}
    return out


# Vimshopaka bala (BPHS ch.7): varga weights out of 20; in each varga a planet in its own sign scores 20,
# otherwise by its compound (D1) relationship with the varga dispositor (exaltation earns nothing extra
# as JHora; some commentators score it 20). Scorpio/Aquarius dispositors are Mars/Saturn (Parashari).
VIMSHOPAKA = {
    "shadvarga": {"D1": 6, "D2": 2, "D3": 4, "D9": 5, "D12": 2, "D30": 1},
    "saptavarga": {"D1": 5, "D2": 2, "D3": 3, "D7": 2.5, "D9": 4.5, "D12": 2, "D30": 1},
    "dashavarga": {"D1": 3, "D2": 1.5, "D3": 1.5, "D7": 1.5, "D9": 1.5, "D10": 1.5, "D12": 1.5, "D16": 1.5,
                   "D30": 1.5, "D60": 5},
    "shodashavarga": {"D1": 3.5, "D2": 1, "D3": 1, "D4": 0.5, "D7": 0.5, "D9": 3, "D10": 0.5, "D12": 0.5,
                      "D16": 2, "D20": 0.5, "D24": 0.5, "D27": 0.5, "D30": 1, "D40": 0.5, "D45": 0.5, "D60": 4},
}
VIMSHOPAKA_POINTS = {2: 18, 1: 15, 0: 10, -1: 7, -2: 5}


def vimshopaka(chart: Chart) -> dict[str, dict[str, float]]:
    from jyotish_kit.facts.builders.placements import signs
    rel = relationships(chart)
    out = {p: {} for p in SEVEN}
    for scheme, weights in VIMSHOPAKA.items():
        for p in SEVEN:
            total = 0.0
            for v, w in weights.items():
                sign = signs(chart, v)[p]
                lord = SIGN_LORDS[sign]
                pts = 20 if lord == p else VIMSHOPAKA_POINTS[rel[p, lord][2]]
                total += w * pts / 20
            out[p][scheme] = total
    return out


def _wars(chart: Chart):
    from jyotish_kit.facts.builders import dignity
    return [f.attrs for f in dignity.build(chart) if f.kind == FactKind.war]


def _sign_class(lon: float) -> str:
    sign, deg = int(lon // 30), lon % 30
    if sign in (2, 5, 6, 10) or (sign == 8 and deg < 15):
        return "nara"
    if sign in (3, 11) or (sign == 9 and deg >= 15):
        return "jalachara"
    if sign == 7:
        return "keeta"
    return "chatushpada"


STRONG_HOUSE = {"nara": 1, "jalachara": 4, "keeta": 7, "chatushpada": 10}


def bhava_madhya(chart: Chart) -> list[float]:
    """Sripati bhava madhyas: Asc, MC and their opposites, quadrants trisected (= Porphyry cusps)."""
    asc, mc = chart.placidus_cusps[0], chart.placidus_cusps[9]
    ic, dsc = (mc + 180) % 360, (asc + 180) % 360
    out = [0.0] * 12
    for start, end, h in ((asc, ic, 0), (ic, dsc, 3), (dsc, mc, 6), (mc, asc, 9)):
        arc = (end - start) % 360
        for k in range(3):
            out[h + k] = (start + arc * k / 3) % 360
    return out


def bhava_bala(chart: Chart, sb: dict) -> dict[int, dict[str, float]]:
    """Bhavadhipati (lord's shadbala) + bhava dig bala + bhava drishti bala (Raman: Jupiter, Mercury full)."""
    ben = benefics(chart)
    bm = bhava_madhya(chart)
    lagna = chart.bodies["Lagna"].sign
    out = {}
    for h in range(1, 13):
        lord = SIGN_LORDS[(lagna + h - 1) % 12]
        d = abs(h - STRONG_HOUSE[_sign_class(bm[h - 1])]) % 12
        dig_b = 60 - 10 * min(d, 12 - d)
        drishti_b = 0.0
        for q in SEVEN:
            v = drishti(bm[h - 1] - chart.bodies[q].lon, q)
            drishti_b += (1 if q in ben else -1) * (v if q in ("Jupiter", "Mercury") else v / 4)
        total = sb[lord]["total"] + dig_b + drishti_b
        out[h] = {"adhipati": sb[lord]["total"], "dig": float(dig_b), "drishti": drishti_b, "total": total,
                  "rupas": total / 60}
    return out


def build(chart: Chart) -> list[Fact]:
    sb = shadbala(chart)
    for p, v in vimshopaka(chart).items():
        sb[p] |= {f"vimshopaka.{k}": x for k, x in v.items()}
    facts = [Fact(id=f"shadbala:D1:{p}", kind=FactKind.shadbala, subject=p,
                  attrs=row | {"strong": row["ratio"] >= 1}) for p, row in sb.items()]
    ranked = sorted(sb, key=lambda p: sb[p]["ratio"], reverse=True)
    for f in facts:
        f.attrs["rank"] = ranked.index(f.subject) + 1
    facts += [Fact(id=f"bhava_bala:D1:H{h}", kind=FactKind.bhava_bala, subject=f"H{h}",
                   attrs=row) for h, row in bhava_bala(chart, sb).items()]
    return facts
