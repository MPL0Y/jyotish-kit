"""Plain-text (Markdown) kundli: every computed layer, with the basis and the reliability of each part.

No interpretation: this is the fact base a reading starts from.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from jyotish_kit.facts.builders.ashtakavarga import bav
from jyotish_kit.facts.builders.dashas import kalachakra, rasi, vimshottari, yogini
from jyotish_kit.facts.builders.vargas import VARGAS
from jyotish_kit.facts.transits import sade_sati_periods, transit_facts
from jyotish_kit.facts.varshaphal import annual_chart, muntha, office_bearers, solar_return, year_lord
from jyotish_kit.kundli import Kundli
from jyotish_kit.models import PLANETS, SEVEN, SIGN_LORDS, SIGNS

ABBR = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa",
        "Rahu": "Ra", "Ketu": "Ke", "Lagna": "La"}


def dms(x: float) -> str:
    d, rest = divmod(round(x * 3600), 3600)
    return f"{d}°{rest // 60:02d}'{rest % 60:02d}\""


def sign_dms(lon: float) -> str:
    return f"{SIGNS[int(lon // 30)][:3]} {dms(lon % 30)}"


def table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _running(periods, when):
    return [p for p in periods if p.start <= when < p.end]


def report(k: Kundli, now: datetime | None = None) -> str:
    c, f = k.chart, k.facts
    now = now or datetime.now(timezone.utc)
    tz = ZoneInfo(k.birth.tz_name)
    loc = lambda t: t.astimezone(tz).strftime("%Y-%m-%d %H:%M")  # noqa: E731
    get = lambda i: f.get(i).attrs  # noqa: E731
    pan, ava = get("panchanga:birth"), get("avakahada:birth")
    L = []
    w = L.append

    w(f"# Kundli — {k.birth.place_name or 'birth chart'}\n")
    w("## 1. Birth data and computation basis\n")
    w(table(["Item", "Value"], [
        ["Local time", f"{k.birth.dt_local:%Y-%m-%d %H:%M:%S} {k.birth.tz_name} (±{k.birth.time_uncertainty_min:g} min)"],
        ["UTC / JD (UT)", f"{c.utc:%Y-%m-%d %H:%M:%S} / {c.jd_ut:.6f}"],
        ["Place", f"{k.birth.lat:.6f}, {k.birth.lon:.6f}"],
        ["Ayanamsa", f"{k.config.ayanamsa} {dms(c.ayanamsa)} (KP {dms(c.ayanamsa_kp)})"],
        ["Sunrise / sunset of the Vedic day", f"{loc(c.sunrise)} / {loc(c.sunset)}; next sunrise {loc(c.next_sunrise)}"],
        ["Birth in", "day" if c.is_day else "night"],
        ["Houses", "whole sign (Parashari); Placidus cusps for KP; Sripati for bhava chalit"],
        ["Nodes / positions", f"{k.config.node} node; apparent geocentric, Swiss Ephemeris files"],
    ]))

    w("\n## 2. Panchanga and avakahada\n")
    w(table(["Limb", "Value"], [
        ["Vara (Vedic weekday)", f"{pan['vara']} (lord {pan['vara_lord']})"],
        ["Tithi", f"{pan['paksha']} {pan['tithi']} (#{pan['tithi_number']}, {pan['tithi_elapsed']:.0%} elapsed)"],
        ["Nakshatra", f"{pan['nakshatra']} pada {pan['pada']} (lord {pan['nakshatra_lord']})"],
        ["Yoga / karana", f"{pan['yoga']} / {pan['karana']}"],
        ["Lunar month", f"{'Adhika ' if pan['adhika'] else ''}{pan['amanta']} (amanta), "
                        f"{'Adhika ' if pan['adhika'] else ''}{pan['purnimanta']} (purnimanta); ritu {pan['ritu']}"],
        ["Ayana", pan["ayana"]],
        ["Moon sign / lord", f"{ava['rashi']} / {ava['rashi_lord']}"],
        ["Varna / vashya / yoni / gana / nadi",
         f"{ava['varna']} / {ava['vashya']} / {ava['yoni']} / {ava['gana']} / {ava['nadi']}"],
    ]))

    w("\n## 3. Grahas\n")
    rows = []
    sb = {p: get(f"shadbala:D1:{p}") for p in SEVEN}
    for p in (*PLANETS, "Lagna"):
        pl, sv = get(f"placement:D1:{p}"), get(f"sensitive:D1:{p}")
        dig = f.get(f"dignity:D1:{p}")
        flags = [x for x in ("vargottama", "rashi_sandhi", "gandanta", "pushkara_navamsa", "pushkara_bhaga",
                             "mrityu_bhaga") if sv.get(x)]
        if f.get(f"combustion:D1:{p}"):
            flags.append("combust")
        if pl["retro"] and p not in ("Rahu", "Ketu"):
            flags.append("retrograde")
        fn = f.get(f"functional:D1:{p}")
        rows.append([p, sign_dms(pl["longitude"]), f"{pl['nakshatra']} {pl['pada']} ({ABBR[pl['nakshatra_lord']]})",
                     pl["house"], sv.get("chalit_bhava", ""), dig.attrs["status"].replace("_", " ") if dig else "",
                     fn.attrs["nature"].replace("_", " ") if fn else "",
                     f"{sb[p]['rupas']:.2f} ({sb[p]['ratio']:.2f}×)" if p in sb else "",
                     f"{sb[p]['vimshopaka.shodashavarga']:.1f}" if p in sb else "",
                     get(f"avastha:D1:{p}")["baladi"] if f.get(f"avastha:D1:{p}") else "",
                     ", ".join(flags).replace("_", " ")])
    w(table(["Graha", "Longitude", "Nakshatra", "House", "Chalit", "Dignity", "Functional", "Shadbala rupas",
             "Vimshopaka /20", "Baladi", "Flags"], rows))
    k8 = {x.subject: x.object for x in f.query("karaka")}
    w(f"\nChara karakas: {', '.join(f'{r} {p}' for r, p in k8.items())}.")
    ex = f.query("exchange", "D1")
    if ex:
        w("Exchanges: " + "; ".join(f"{x.subject}↔{x.object} (houses {x.attrs['houses'][0]}–{x.attrs['houses'][1]}, "
                                    f"{x.attrs['type']})" for x in ex) + ".")
    wars = f.query("war")
    if wars:
        w("Graha yuddha: " + "; ".join(f"{x.attrs['winner']} beats {x.attrs['loser']}" for x in wars) + ".")
    fl = {p: get(f"functional:D1:{p}") for p in SEVEN}
    w("Yogakaraka: " + (", ".join(p for p, a in fl.items() if a["yogakaraka"]) or "none")
      + ". Marakas: " + ", ".join(p for p, a in fl.items() if a["maraka"])
      + ". Badhaka: " + ", ".join(p for p, a in fl.items() if a["badhaka"])
      + ". Kendradhipati dosha: " + (", ".join(p for p, a in fl.items() if a["kendradhipati_dosha"]) or "none") + ".")

    w("\n## 4. Bhavas\n")
    sav = [sum(r[i] for r in bav(c).values()) for i in range(12)]
    rows = []
    for h in range(1, 13):
        lo = f.get(f"lordship:D1:H{h}")
        sign = SIGNS.index(lo.attrs["sign"])
        bb = get(f"bhava_bala:D1:H{h}")
        ar = get(f"argala:D1:H{h}")
        eff = [n for n, a in ar.items() if a["effective"]]
        rows.append([h, lo.attrs["sign"], f"{lo.object} (in {lo.attrs['lord_house']})",
                     ", ".join(ABBR[p] for p in f.occupants(h)), ", ".join(ABBR[p] for p in f.aspects_on(f"H{h}")),
                     sav[sign], f"{bb['rupas']:.2f}", ", ".join(eff)])
    w(table(["House", "Sign", "Lord (placed in)", "Occupants", "Graha drishti from", "SAV", "Bhava bala rupas",
             "Effective argala from"], rows))

    w("\n## 5. Divisional charts (sign of each graha)\n")
    rows = [[v] + [SIGNS.index(f.sign_of(p, v)) + 1 for p in ("Lagna", *PLANETS)] for v in VARGAS]
    w(table(["Varga", *(ABBR[p] for p in ("Lagna", *PLANETS))], rows))
    w("\n(1 = Aries … 12 = Pisces.)")

    w("\n## 6. Special points\n")
    rows = [[x.subject, sign_dms(x.attrs["longitude"]), x.attrs["house"]] for x in f.query("upagraha")]
    rows += [[x.subject, sign_dms(x.attrs["longitude"]) if "longitude" in x.attrs else x.attrs["sign"],
              x.attrs.get("house", "")] for x in f.query("special_lagna")]
    rows += [[x.subject.replace("special_lagna:", ""), x.attrs["sign"], x.attrs["house"]] for x in f.query("arudha")]
    w(table(["Point", "Position", "House"], rows))

    w("\n## 7. Dashas (running now)\n")
    vim = vimshottari.periods(c, 3)
    run = {
        "Vimshottari": _running(vim, now),
        "Yogini": _running(yogini.periods(c, 2), now),
        "Chara (K.N. Rao)": _running(rasi.chara(c, 2), now),
        "Narayana": _running(rasi.narayana(c, 2), now),
        "Kalachakra": _running(kalachakra.periods(c, 2), now),
    }
    rows = [[s, " / ".join(ps[-1].lords) if ps else "", f"{loc(ps[-1].start)} → {loc(ps[-1].end)}" if ps else ""]
            for s, ps in run.items()]
    w(table(["System", "Running", "Innermost period"], rows))
    w("\nVimshottari mahadashas:\n")
    w(table(["Mahadasha", "From", "To"], [[p.lords[0], loc(p.start)[:10], loc(p.end)[:10]]
                                         for p in vim if len(p.lords) == 1]))

    w(f"\n## 8. Gochara on {now:%Y-%m-%d}\n")
    tr = {x.subject: x.attrs for x in transit_facts(c, now) if x.id.count(":") == 2 and x.subject in PLANETS}
    w(table(["Graha", "Sign", "From Lagna", "From Moon", "BAV", "SAV"],
            [[p, a["sign"] + (" (R)" if a["retro"] and p not in ("Rahu", "Ketu") else ""), a["house_from_lagna"],
              a["house_from_moon"], a.get("bav_bindus", ""), a["sav_bindus"]] for p, a in tr.items()]))
    ss = sade_sati_periods(c, now.replace(year=now.year - 1), now.replace(year=now.year + 15))
    if ss:
        w("\nSade Sati spans (next 15 years): " + "; ".join(f"{a:%Y-%m} → {b:%Y-%m} {ph}" for a, b, ph in ss) + ".")

    years = max(n for n in range(0, 130) if solar_return(c, n) <= now)
    a = annual_chart(c, years)
    ob = office_bearers(a, c, years)
    w(f"\n## 9. Varshaphal (year {years + 1}, from {loc(a.utc)})\n")
    m = muntha(c, years)
    w(table(["Item", "Value"], [
        ["Varsha Lagna", SIGNS[a.bodies["Lagna"].sign]],
        ["Muntha", f"{SIGNS[m]} (lord {SIGN_LORDS[m]})"],
        ["Office bearers", ", ".join(f"{k_.replace('_', ' ')} {v}" for k_, v in ob.items())],
        ["Year lord", year_lord(a, c, years)],
    ]))

    w("\n## 10. Reliability\n")
    groups: dict[str, list] = {}
    for x in f.facts:
        if not x.stable:
            groups.setdefault(f"{x.kind.value} {x.varga or ''}".strip(), []).append(x)
    w(f"Birth-time window ±{k.birth.time_uncertainty_min:g} min: {sum(map(len, groups.values()))} of "
      f"{len(f.facts)} facts change inside it.\n")
    w(table(["Kind / varga", "Facts changing", "Least stable (share of window)"],
            [[g, len(xs), ", ".join(f"{x.subject} {x.window_fraction:.0%}" for x in
                                    sorted(xs, key=lambda x: x.window_fraction)[:4])]
             for g, xs in sorted(groups.items(), key=lambda kv: -len(kv[1]))]))
    sens = k.ayanamsa_sensitivity()
    w("\nAyanamsa sensitivity (facts that change if another ayanamsa is used instead of "
      f"{k.config.ayanamsa}):")
    for alt, ids in sens.items():
        key = [i for i in ids if i.split(":")[0] in ("placement", "dignity", "lordship", "exchange")
               and i.split(":")[1] in ("D1", "D9")]
        w(f"- {alt}: {len(ids)} facts; in D1/D9: {', '.join(f'`{i}`' for i in key[:12]) or 'none'}")

    w("\n## 11. Sources and conventions\n")
    srcs = sorted({(x.kind.value, x.source) for x in f.facts})
    w(table(["Fact kind", "Source"], [list(s) for s in srcs]))
    return "\n".join(L) + "\n"
