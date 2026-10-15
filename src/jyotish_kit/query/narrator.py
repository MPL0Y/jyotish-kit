"""Layer 5 narration: structured Judgments and TimeWindows in, cited prose out. Calculates nothing.

The narrator sees only the payload built here. Its prose is checked before it is shown:
- every [citation] must be a rule id present in the payload;
- every paragraph must cite, except headings, paragraphs starting "Note:", and the no-rule verdicts;
- every year and every zodiac sign it names must appear in the payload (no invented dates or positions);
- every school in the payload must be named (disagreements are shown, not averaged away).
A failing draft is retried once with the problems listed; if it still fails, the deterministic template is used.
"""

import json
import re
from datetime import datetime, timezone
from typing import Protocol

from jyotish_kit.models import SIGNS
from jyotish_kit.query.router import Route
from jyotish_kit.synthesis import NO_RULE, NONE_FIRED, Synthesis
from jyotish_kit.timing import windows

NARRATOR_MODEL = "claude-opus-5-5"
MAX_EVIDENCE = 8
SCHOOL_NAMES = {"parashari": "Parashari", "jaimini": "Jaimini", "kp": "KP"}
CITE = re.compile(r"\[([^\[\]]+)\]")


def payload(question: str, syn: Synthesis, r: Route, now: datetime | None = None, years: float = 10) -> dict:
    now = now or datetime.now(timezone.utc)
    start = datetime(r.start_year, 1, 1, tzinfo=timezone.utc) if r.start_year else now
    end = (datetime(r.end_year + 1, 1, 1, tzinfo=timezone.utc) if r.end_year
           else start.replace(year=start.year + int(years)))
    out = {"question": question, "today": now.date().isoformat(), "drafts": syn.drafts,
           "birth_time_window_minutes": syn.k.birth.time_uncertainty_min, "topics": []}
    for t in r.topics:
        schools = []
        for s in syn.schools:
            j = syn.judge(t, s)
            row = {"school": s, "verdict": j.verdict, "score": j.score, "confidence": j.confidence,
                   "triple_confirmation": j.triple, "varga_confirmation": j.varga, "notes": j.notes,
                   "evidence": [{"id": e.rule_id, "name": e.name, "polarity": e.polarity,
                                 "weight": round(e.weight, 2), "themes": e.themes, "source": e.citation,
                                 "adjustments": e.adjustments,
                                 **({"time_sensitive": round(e.factors["stability"], 2)}
                                    if e.factors.get("stability", 1) < 1 else {})}
                                for e in j.evidence[:MAX_EVIDENCE]]}
            if r.timing and j.verdict not in (NO_RULE, NONE_FIRED):
                tm = windows(syn, t, s, start, end)
                row["timing"] = {"from": start.date().isoformat(), "to": end.date().isoformat(), "notes": tm.notes,
                                 "windows": [{"start": w.start.date().isoformat(), "end": w.end.date().isoformat(),
                                              "score": w.score, "dasha_lords": w.lords, "drivers": w.drivers}
                                             for w in tm.windows]}
            schools.append(row)
        out["topics"].append({"topic": t, "schools": schools})
    return out


def rule_ids(p: dict) -> set[str]:
    """Citable ids: rule ids, plus timing:<topic>/<school> for a timing block (its drivers are the source)."""
    return {e["id"] for t in p["topics"] for s in t["schools"] for e in s["evidence"]} | {
        f"timing:{t['topic']}/{s['school']}" for t in p["topics"] for s in t["schools"] if "timing" in s} | {
        d.split()[1] for t in p["topics"] for s in t["schools"] for w in s.get("timing", {}).get("windows", [])
        for d in w["drivers"] if d.startswith("rule ")}


def check(text: str, p: dict) -> list[str]:
    ids, blob, problems = rule_ids(p), json.dumps(p), []
    for c in CITE.findall(text):
        for i in (x.strip() for x in c.split(",")):
            if i not in ids:
                problems.append(f"cites [{i}], which is not a rule id in the input")
    for para in (x.strip() for x in text.split("\n\n")):
        if para and not para.startswith(("#", "Note:")) and NO_RULE not in para and NONE_FIRED not in para and not CITE.search(para):
            problems.append(f"paragraph without a citation: {para[:80]!r}")
    for y in set(re.findall(r"\b(1[89]\d\d|2[01]\d\d)\b", text)):
        if y not in blob:
            problems.append(f"mentions the year {y}, which is not in the input")
    for s in SIGNS:
        if re.search(rf"\b{s}\b", text) and s not in blob:
            problems.append(f"mentions {s}, which is not in the input")
    for s in {s["school"] for t in p["topics"] for s in t["schools"]}:
        if not re.search(s, text, re.I):
            problems.append(f"does not mention the {s} school")
    return problems


class Narrator(Protocol):
    def __call__(self, p: dict, problems: list[str] | None = None) -> str: ...


def template(p: dict, problems: list[str] | None = None) -> str:
    """Deterministic narration (no LLM): the fallback, and what --no-llm prints."""
    out = []
    if p["drafts"]:
        out.append("Note: this answer uses unverified draft rules.")
    for t in p["topics"]:
        out.append(f"## {t['topic'].capitalize()}")
        for s in t["schools"]:
            name = SCHOOL_NAMES.get(s["school"], s["school"])
            if s["verdict"] in (NO_RULE, NONE_FIRED):
                out.append(f"{name}: {s['verdict']}.")
                continue
            ev = s["evidence"]
            pro = [e for e in ev if e["polarity"] > 0][:3]
            con = [e for e in ev if e["polarity"] < 0][:3]
            line = (f"{name}: {s['verdict']} (score {s['score']:+.2f}, "
                    f"confidence {s['confidence']:.2f}).")
            if pro:
                line += " For: " + "; ".join(f"{e['name']} [{e['id']}]" for e in pro) + "."
            if con:
                line += " Against: " + "; ".join(f"{e['name']} [{e['id']}]" for e in con) + "."
            if not pro and not con:
                line += " Only neutral rules fired: " + "; ".join(f"{e['name']} [{e['id']}]" for e in ev[:3]) + "."
            tri = s["triple_confirmation"]
            if tri.get("components"):
                line += f" Bhava/bhavesh/karaka: {tri['status']}."
            if s["varga_confirmation"].get("status") not in (None, "not applicable"):
                line += f" {s['varga_confirmation']['varga']}: {s['varga_confirmation']['status']}."
            sens = [e["id"] for e in ev if "time_sensitive" in e]
            if sens:
                line += " Birth-time sensitive: " + ", ".join(f"[{i}]" for i in sens) + "."
            out.append(line)
            tm = s.get("timing")
            if tm:
                ws = tm["windows"]
                if ws:
                    out.append(f"{name} windows [timing:{t['topic']}/{s['school']}]: " + "; ".join(
                        f"{w['start']} to {w['end']} ({'/'.join(w['dasha_lords'])})" for w in ws) + ".")
                for n in tm["notes"]:
                    if not n.startswith("uses unverified"):
                        out.append(f"Note: {s['school']}: {n}.")
    return "\n\n".join(out)


PROMPT = """You narrate a Vedic astrology (Jyotish) answer from the JSON below and nothing else.

Rules:
- State nothing that is not in the JSON: no planet positions, signs, houses, yogas, dates or outcomes of your own.
- Cite inline with the rule id in square brackets after each claim, e.g. [BPHS.24.L7H10]. Use only ids in the JSON.
  Cite a school's time windows as [timing:<topic>/<school>], e.g. [timing:marriage/kp].
  Every paragraph needs a citation, except a paragraph that starts "Note:" or says "{no_rule}" or
  "{none_fired}" (use those exact phrases for a school with that verdict).
- Keep schools separate (parashari, jaimini, kp). Name every school present; if they disagree, say so plainly.
- Give each school's confidence, and mention evidence marked time_sensitive (birth time is a window of
  {window} minutes).
- For timing, give the windows as ranges with their drivers; never a single date, never a certain outcome.
- If "drafts" is true, start with "Note: this answer uses unverified draft rules."
- Plain, warm, direct English; short paragraphs; no headings beyond one per topic ("## Topic").

Question: {question}

JSON:
{data}
"""


def claude(client=None):
    def narrate(p: dict, problems: list[str] | None = None) -> str:
        nonlocal client
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        msgs = [{"role": "user", "content": PROMPT.format(no_rule=NO_RULE, none_fired=NONE_FIRED, window=p["birth_time_window_minutes"],
                                                          question=p["question"], data=json.dumps(p, indent=1))}]
        if problems:
            msgs.append({"role": "user", "content": "Your previous draft had these problems; fix them:\n- "
                         + "\n- ".join(problems)})
        return client.messages.create(model=NARRATOR_MODEL, max_tokens=2000, messages=msgs).content[0].text
    return narrate


def narrate(p: dict, narrator: Narrator) -> tuple[str, list[str]]:
    """(text, notes). Checked narration, one retry, then the template."""
    text = narrator(p)
    problems = check(text, p)
    if problems:
        text = narrator(p, problems)
        problems = check(text, p)
    if problems:
        return template(p), [f"narration rejected ({len(problems)} problems), template used: " + "; ".join(problems[:3])]
    return text, []
