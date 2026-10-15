import json
from datetime import datetime, time, timedelta
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
import yaml
from rich.console import Console
from rich.table import Table

from jyotish_kit.ephemeris.uncertainty import window_offsets
from jyotish_kit.facts.builders.dashas.vimshottari import active, balance_at_birth
from jyotish_kit.kundli import Kundli
from jyotish_kit.models import SIGNS, BirthData, LifeEvent

app = typer.Typer(no_args_is_help=True)
con = Console()


def _load(path: Path) -> Kundli:
    return Kundli.from_birth(BirthData(**yaml.safe_load(path.read_text())["birth"]))


def _fmt_dur(days: float) -> str:
    return f"{days:.1f} d" if days < 60 else f"{days / 365.2425:.1f} y"


def _dms(x: float) -> str:
    d, m = divmod(round(x * 3600), 3600)
    return f"{d:02d}°{m // 60:02d}'{m % 60:02d}\""


@app.command()
def chart(person: Path, local: bool = True):
    """Positions, D1/D9/D10 signs, stability across the birth window, Vimshottari."""
    k = _load(person)
    c, f, tz = k.chart, k.facts, ZoneInfo(k.birth.tz_name)
    fmt = (lambda t: t.astimezone(tz).strftime("%Y-%m-%d %H:%M")) if local else (lambda t: t.isoformat())
    con.print(f"[bold]{k.birth.place_name}[/] {k.birth.dt_local} {k.birth.tz_name} "
              f"(UTC{k.birth.utc_offset()}) ± {k.birth.time_uncertainty_min} min")
    con.print(f"Ayanamsa {k.config.ayanamsa} {_dms(c.ayanamsa)} · node {k.config.node} · "
              f"sunrise {fmt(c.sunrise)} sunset {fmt(c.sunset)} · {'day' if c.is_day else 'night'} birth")

    t = Table("Body", "Sign", "Deg", "R", "Nakshatra", "Pd", "H", "D9", "D10", "Dignity", "Stable")
    for name, b in c.bodies.items():
        p = f.get(f"placement:D1:{name}")
        d9, d10 = (f.get(f"placement:{v}:{name}") for v in ("D9", "D10"))
        dig = f.get(f"dignity:D1:{name}")
        unstable = [x.varga for x in (p, d9, d10) if not x.stable]
        t.add_row(name, p.attrs["sign"], _dms(b.deg), "R" if b.retro else "", p.attrs["nakshatra"],
                  str(p.attrs["pada"]), str(p.attrs["house"]), d9.attrs["sign"], d10.attrs["sign"],
                  dig.attrs["status"] if dig else "",
                  "yes" if not unstable else f"[red]no ({','.join(unstable)})[/]")
    con.print(t)
    rng = f.get("placement:D1:Lagna").attrs.get("degree_range")
    if rng:
        con.print(f"Lagna degree across window: {_dms(rng[0])} – {_dms(rng[1])} {SIGNS[c.bodies['Lagna'].sign]}")
    for x in f.query("combustion") + f.query("war"):
        con.print(f"{x.kind}: {x.subject} {x.attrs}")

    lord, left = balance_at_birth(c)
    con.print(f"\nVimshottari ({k.config.dasha_year_days} d/yr): balance {lord} {left:.4f} y")
    t = Table("Maha", "Antar", "Start", "End", "Start spread in window")
    for x in f.query("dasha_period"):
        if x.attrs["level"] <= 2:
            lo, hi = x.attrs.get("start_range", (x.attrs["start"],) * 2)
            t.add_row(*(x.attrs["lords"] + [""])[:2], fmt(x.attrs["start"]), fmt(x.attrs["end"]),
                      f"±{(hi - lo).days / 2:.0f} d")
    con.print(t)


@app.command()
def facts(person: Path, kind: str | None = None, varga: str | None = None, subject: str | None = None,
          unstable: bool = False):
    """Dump facts, optionally only time-sensitive ones."""
    k = _load(person)
    for x in k.facts.query(kind, varga, subject):
        if not unstable or not x.stable:
            con.print(f"{x.id:40} {x.object or '':8} {'' if x.stable else f'[red]{x.window_fraction:.2f}[/] '}{x.attrs}")


@app.command()
def events(person: Path):
    """Vimshottari periods active at each logged event, by birth second across the window."""
    k = _load(person)
    tz = ZoneInfo(k.birth.tz_name)
    evs = [LifeEvent(**e) for e in yaml.safe_load(person.read_text()).get("known_life_events", [])]
    births = [k.birth.dt_local + timedelta(seconds=o) for o in window_offsets(k.birth)]
    t = Table("Event", "Date", "Maha/Antar", "Pratyantar by birth time")
    for e in evs:
        start = datetime.combine(e.date, time(), tz)
        end = datetime.combine(e.end or e.date, time(), tz) + timedelta(days=1)
        labels = [(" + ".join(p.lords[2] for p in ps), {p.lords[:2] for p in ps})
                  for ps in (active(c, start, end) for c in k.charts)]
        runs = [(lab, [b for b, _ in grp]) for lab, grp in groupby(zip(births, labels), key=lambda x: x[1][0])]
        ma = sorted({"/".join(x) for _, mas in labels for x in mas})
        t.add_row(e.description, f"{e.date}" + (f" .. {e.end}" if e.end else ""), "\n".join(ma),
                  "\n".join(f"{bs[0]:%H:%M:%S}–{bs[-1]:%H:%M:%S}  {lab}" for lab, bs in runs))
    con.print(t)


@app.command()
def varsha(person: Path, year: int, lat: float | None = None, lon: float | None = None):
    """Tajika annual chart for the year beginning on the `year`-th birthday: office bearers, sahams, mudda dasha.
    --lat/--lon cast it for the place of residence instead of the birth place."""
    from jyotish_kit.facts.varshaphal import facts as varsha_facts
    k = _load(person)
    tz = ZoneInfo(k.birth.tz_name)
    for x in varsha_facts(k.chart, year, lat=lat, lon=lon):
        if x.attrs.get("system") == "mudda":
            if x.attrs["level"] == 1:
                con.print(f"{x.id:28} {x.attrs['start'].astimezone(tz):%Y-%m-%d %H:%M} → "
                          f"{x.attrs['end'].astimezone(tz):%Y-%m-%d %H:%M}")
        else:
            con.print(f"{x.id:28} {x.object or '':8} {x.attrs}")


@app.command()
def report(person: Path, out: Path | None = None):
    """Full descriptive kundli in Markdown: basis, panchanga, grahas, bhavas, vargas, points, dashas,
    transits, varshaphal, reliability and sources."""
    from jyotish_kit.report import report as render
    text = render(_load(person))
    if out:
        out.write_text(text)
        con.print(f"wrote {out}")
    else:
        print(text)


def _schools(person: Path, school: str | None) -> tuple[str, ...]:
    if school:
        return (school,)
    return tuple(yaml.safe_load(person.read_text()).get("preferred_schools") or ("parashari", "jaimini", "kp"))


@app.command()
def judge(person: Path, topic: str | None = None, school: str | None = None, drafts: bool = False,
          raw: bool = False):
    """Per-topic verdicts, one per school (never merged). --drafts allows unverified rules (labelled);
    --raw prints every piece of evidence with its weight factors, meta-rule adjustments and fact ids."""
    from jyotish_kit.synthesis import TOPICS, Synthesis
    syn = Synthesis(_load(person), include_drafts=drafts, schools=_schools(person, school))
    if drafts:
        con.print("[yellow]UNVERIFIED: draft rules included[/yellow]")
    t = Table("topic", "school", "verdict", "score", "conf", "bhava/bhavesh/karaka", "varga", "top evidence")
    for name in [topic] if topic else TOPICS:
        for s in syn.schools:
            j = syn.judge(name, s)
            tri = j.triple.get("components")
            t.add_row(name, s, j.verdict, f"{j.score:+.2f}", f"{j.confidence:.2f}",
                      f"{tri['bhava']:+d}/{tri['bhavesh']:+d}/{tri['karaka']:+d} {j.triple['status']}" if tri else "",
                      f"{j.varga.get('varga', '')} {j.varga.get('status', '')}" if j.varga.get("varga") else "",
                      "; ".join(f"{e.name} {e.signed:+.2f}" for e in (j.supporting[:2] + j.opposing[:2])))
            if raw:
                for e in j.evidence:
                    con.print(f"[bold]{name}/{s}[/bold] {e.rule_id} {e.signed:+.3f} [{e.status}] {e.citation}",
                              highlight=False)
                    con.print(f"    factors {', '.join(f'{k}={v:.2f}' for k, v in e.factors.items())}"
                              + "".join(f"\n    {a}" for a in e.adjustments), highlight=False)
                    con.print(f"    facts {', '.join(e.matched)}", highlight=False)
                for n in j.notes:
                    con.print(f"    note: {n}", highlight=False)
    con.print(t)


@app.command()
def when(person: Path, topic: str, years: float = 10, start: str | None = None, school: str | None = None,
         drafts: bool = False, top: int = 5):
    """The best 3-5 windows in which a topic is activated, with drivers (from today unless --start YYYY-MM-DD)."""
    from datetime import timezone
    from jyotish_kit.synthesis import Synthesis
    from jyotish_kit.timing import windows
    t0 = datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if start else datetime.now(timezone.utc)
    t1 = t0 + timedelta(days=365.2425 * years)
    syn = Synthesis(_load(person), include_drafts=drafts, schools=_schools(person, school))
    if drafts:
        con.print("[yellow]UNVERIFIED: draft rules included[/yellow]")
    for s in syn.schools:
        tm = windows(syn, topic, s, t0, t1, top=top)
        con.print(f"[bold]{topic} / {s}[/bold]: natal promise {tm.promise} ({tm.promise_score:+.2f})")
        for n in tm.notes:
            con.print(f"  note: {n}", highlight=False)
        for w in tm.windows:
            con.print(f"  {w.start:%Y-%m-%d} → {w.end:%Y-%m-%d}  score {w.score:.2f}  ({'/'.join(w.lords)})",
                      highlight=False)
            for d in w.drivers:
                con.print(f"      {d}", highlight=False)


@app.command()
def ask(person: Path, question: str, drafts: bool = False, raw: bool = False, llm: bool = True,
        school: str | None = None, years: float = 10):
    """Answer a question in cited prose built only from the Judgments and time windows. --raw prints the
    evidence with no LLM; --no-llm uses keyword routing and the deterministic template."""
    import os
    from jyotish_kit.query.narrator import claude, narrate, payload, template
    from jyotish_kit.query.router import route
    from jyotish_kit.synthesis import Synthesis
    use_llm = llm and bool(os.environ.get("ANTHROPIC_API_KEY"))
    r = route(question, use_llm=use_llm)
    if not r.topics:
        con.print("Could not tell which part of the chart this asks about; name a topic (career, marriage, ...).")
        raise typer.Exit(1)
    con.print(f"[dim]topics: {', '.join(r.topics)}; timing: {r.timing}; routed by {r.via}[/dim]")
    syn = Synthesis(_load(person), include_drafts=drafts, schools=_schools(person, school))
    p = payload(question, syn, r, years=years)
    if raw:
        print(json.dumps(p, indent=1, default=str))
        return
    text, notes = narrate(p, claude()) if use_llm else (template(p), ["no ANTHROPIC_API_KEY or --no-llm: template"])
    print(text)
    for n in notes:
        con.print(f"[dim]{n}[/dim]", highlight=False)


corpus_app = typer.Typer(no_args_is_help=True, help="Rule corpus: validate, draft, review, verify.")
app.add_typer(corpus_app, name="corpus")


@corpus_app.command("validate")
def corpus_validate(drafts: bool = True):
    """Fail on schema violations, unknown primitives, duplicate ids, missing citations."""
    from jyotish_kit.corpus import load, validate
    errs = validate(include_drafts=drafts)
    for e in errs:
        con.print(f"[red]✗[/red] {e}", highlight=False)
    if errs:
        raise typer.Exit(1)
    con.print(f"[green]valid[/green]: {len(load(include_drafts=drafts))} rules")


@corpus_app.command("schema")
def corpus_schema():
    """Regenerate corpus/schema.json from the Rule model."""
    import json
    from jyotish_kit.corpus import SCHEMA_PATH, schema
    SCHEMA_PATH.write_text(json.dumps(schema(), indent=2) + "\n")
    con.print(f"wrote {SCHEMA_PATH}")


@corpus_app.command("list")
def corpus_list(school: str | None = None, tag: str | None = None, status: str | None = None, drafts: bool = False):
    from jyotish_kit.corpus import load
    for r in load(include_drafts=drafts):
        if (school and r.school != school) or (tag and tag not in r.tags) or (status and r.status != status):
            continue
        con.print(f"{r.id:40} {r.status:9} {r.effect.polarity:+d} {r.name}", highlight=False)


@corpus_app.command("draft")
def corpus_draft(passage: Path, school: str = typer.Option(...), text: str = typer.Option(...),
                 chapter: str = typer.Option(...), verse: str | None = None, edition: str = typer.Option(...)):
    """LLM-draft rules (status: draft) from a passage file into corpus/drafts/<school>/. Needs ANTHROPIC_API_KEY
    and the `llm` extra."""
    from jyotish_kit.corpus.ingest import draft
    out, errs = draft(passage.read_text(), school, text, chapter, verse, edition)
    con.print(f"wrote {out}")
    for e in errs:
        con.print(f"[yellow]still invalid[/yellow] {e}", highlight=False)


@corpus_app.command("review")
def corpus_review(rule_id: str, search: int = 0, verify: bool = False, dispute: bool = False,
                  by: str | None = None, note: str | None = None):
    """Show a rule and where it fires on the test charts (and N random charts); optionally record a verdict."""
    from jyotish_kit.corpus.ingest import review, verify as record
    r, firings = review(rule_id, search)
    con.print(yaml.safe_dump(r.model_dump(exclude_none=True), sort_keys=False, allow_unicode=True), highlight=False)
    t = Table("chart", "result", "evidence")
    for n, f in firings.items():
        res = f.error or ("[green]fires[/green]" if f.fired else "cancelled" if f.cancelled else "-")
        t.add_row(n, res, ", ".join(f.matched + [f"cancel: {c}" for c in f.cancelled_by]))
    con.print(t)
    con.print(f"fires on {sum(f.fired for f in firings.values())}/{len(firings)} charts")
    if verify or dispute:
        record(rule_id, "verified" if verify else "disputed", by, note)
        con.print(f"recorded {'verified' if verify else 'disputed'} in verifications.yaml")


@app.command()
def rules(person: Path, school: str | None = None, tag: str | None = None, drafts: bool = True,
          all: bool = False):
    """Rules that fire on a chart, with the facts that made them fire. Drafts are shown (and marked) by default,
    since nothing is verified yet; synthesis will use verified rules only."""
    from jyotish_kit.corpus import fire, load
    k = _load(person)
    t = Table("rule", "status", "pol", "name", "evidence")
    for r in load(include_drafts=drafts):
        if (school and r.school != school) or (tag and tag not in r.tags):
            continue
        f = fire(r, k.facts)
        if f.fired or all or f.error:
            note = f.error or ("" if f.fired else "cancelled: " + ", ".join(f.cancelled_by) if f.cancelled else "-")
            t.add_row(r.id, r.status, f"{r.effect.polarity:+d}", r.name, note or ", ".join(f.matched))
    con.print(t)


if __name__ == "__main__":
    app()


event_app = typer.Typer(no_args_is_help=True, help="Life-event log (SQLite, people/events.db).")
app.add_typer(event_app, name="event")


def _events(person: Path) -> list[LifeEvent]:
    """The person's logged events; the yaml's known_life_events are imported first (idempotent)."""
    from jyotish_kit.feedback import events as E
    E.import_yaml(person)
    return E.events(person.stem)


@event_app.command("add")
def event_add(person: Path, date: str, domain: str, description: str = "", end: str | None = None,
              precision: str = "day", polarity: int | None = None):
    """Log an event: DATE YYYY-MM-DD, DOMAIN a topic (career, marriage, ...) or one of its domains."""
    from jyotish_kit.feedback import events as E
    e = LifeEvent(date=date, end=end, precision=precision, domain=domain, description=description, polarity=polarity)
    if E.topic_of(domain) is None:
        raise typer.BadParameter(f"{domain!r} maps to no topic; see synthesis/topics.yaml")
    con.print("logged" if E.add(person.stem, e) else "already logged")


@event_app.command("list")
def event_list(person: Path):
    from jyotish_kit.feedback.events import topic_of
    t = Table("date", "span", "domain", "topic", "polarity", "description")
    for e in _events(person):
        d0, d1 = e.span()
        t.add_row(str(e.date), "" if d0 == d1 else f"{d0} .. {d1}", e.domain, topic_of(e.domain) or "-",
                  "" if e.polarity is None else f"{e.polarity:+d}", e.description)
    con.print(t)


@app.command()
def backtest(person: Path, drafts: bool = False, pad: int = 30, school: str | None = None):
    """How the timing model and each rule's timing condition line up with logged events, against chance.
    Reports only; never edits rules."""
    from jyotish_kit.feedback.backtest import backtest as run
    from jyotish_kit.synthesis import Synthesis
    syn = Synthesis(_load(person), include_drafts=drafts, schools=_schools(person, school))
    if drafts:
        con.print("[yellow]UNVERIFIED: draft rules included[/yellow]")
    bt = run(syn, _events(person), pad=pad)
    con.print(f"events matched within ±{pad} days; percentile 0.5 = chance, z > 2 would be notable")
    for n in bt.skipped:
        con.print(f"  skipped: {n}", highlight=False)
    t = Table("school", "source", "mean percentile", "z")
    for s, src in bt.sources.items():
        for name, (m, z) in src.items():
            t.add_row(s, name, f"{m:.2f}", f"{z:+.2f}")
    con.print(t)
    t = Table("event", "topic", "school", "lords", "total pct", "by source")
    for e in bt.events:
        t.add_row(f"{e.date} {e.description}", e.topic, e.school, e.period, f"{e.percentile.get('total', 0.5):.2f}",
                  " ".join(f"{k}={v:.2f}" for k, v in e.percentile.items() if k != "total"))
    con.print(t)
    t = Table("rule", "topic", "hits/events", "baseline", "lift")
    for r in bt.rules:
        t.add_row(r.rule_id, r.topic, f"{r.hits}/{r.events}", f"{r.baseline:.2f}",
                  "-" if r.lift is None else f"{r.lift:.2f}")
    con.print(t)
    for s, (n, h, b, lift) in bt.schools.items():
        con.print(f"{s}: rule timing hit {h}/{n} event-rule pairs, baseline {b:.2f}, lift "
                  + ("-" if lift is None else f"{lift:.2f}"), highlight=False)


@app.command()
def rectify(person: Path, window: float | None = None, step: float = 1, school: str = "parashari",
            top: int = 10, pad: int = 30, null: int = 200):
    """Rank candidate birth times by how well Vimshottari activations (D1 and the topic's varga) fit the
    logged events, with a chance baseline from randomly re-dated events. A ranking, not an answer."""
    from jyotish_kit.feedback.backtest import rectify as run
    k = _load(person)
    r = run(k.birth, _events(person), window_min=window, step_min=step, school=school, pad=pad, null=null)
    t = Table("offset", "birth time", "score", "z", "D1", "D9", "D10")
    for c in r.candidates[:top] + [c for c in r.candidates[top:] if c.offset_min == 0]:
        t.add_row(f"{c.offset_min:+g} min", f"{c.dt_local:%H:%M:%S}", f"{c.score:.2f}", f"{c.z:+.2f}", *c.lagna.values())
    con.print(t)
    nb = r.null_best
    con.print(f"best score by chance (events at random dates, {len(nb)} runs): median {nb[len(nb) // 2]:.2f}, "
              f"95th percentile {nb[int(0.95 * len(nb))]:.2f}; p = {r.p_value:.3f}"
              + ("" if r.p_value < 0.05 else ": the top candidate is not distinguishable from chance"),
              highlight=False)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable hot reload for development"),
):
    """Launch the JyotishKit REST API server."""
    import uvicorn
    con.print(f"[bold green]Starting JyotishKit API on http://{host}:{port}[/]")
    con.print(f"[cyan]Interactive OpenAPI docs available at: http://{host}:{port}/docs[/]")
    uvicorn.run("jyotish_kit.api.app:app", host=host, port=port, reload=reload)

