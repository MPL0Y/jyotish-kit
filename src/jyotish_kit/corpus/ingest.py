"""Corpus ingestion: an LLM drafts rules from a passage, a human reviews and verifies them.

`draft` writes rules with status: draft to corpus/drafts/<school>/; they never reach synthesis.
`review` shows a rule and where it fires; `verify` records the human verdict in verifications.yaml; a verified draft is then moved by hand
into corpus/<school>/ (drafts are never loaded for synthesis).
The passage itself is never stored: the prompt asks for a paraphrase and a citation only.
"""

import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from jyotish_kit.corpus import DRAFTS, VERIFICATIONS, fire, load, rule_errors, verifications
from jyotish_kit.dsl.evaluator import reference
from jyotish_kit.kundli import Kundli
from jyotish_kit.models import DOMAINS, BirthData, Rule

ROOT = Path(__file__).resolve().parents[3]
MODEL = "claude-opus-5-5"

PROMPT = """You convert a passage of a classical Jyotish text into rules for a rule engine.

Output only YAML: a mapping with one key `rules`, a list of rules. Each rule has
id (<TEXT>.<chapter>.<Name>, e.g. BPHS.24.L7H10), name, school ({school}),
source {{text, chapter, verse, edition, paraphrase}}, condition, optional cancels_if, optional varga (D1 default,
D9 etc., or KP), effect {{domains, polarity -2..2, themes}}, optional timing,
classical_strength (primary | supporting | minority_view), tags, status: draft.

Rules:
- paraphrase is YOUR OWN condensed wording of what the passage says. Never copy or translate the passage verbatim.
- Cite exactly: text "{text}", chapter {chapter}, verse {verse}, edition "{edition}". Do not invent verse numbers.
- condition, cancels_if and timing are expressions in the DSL below; use only these names.
  timing may use dasha_lord, antardasha_lord, pratyantardasha_lord; condition may not.
- domains must be from: {domains}
- If the passage cannot be expressed in the DSL, output `rules: []` and nothing else.

DSL:
{dsl}

Passage:
{passage}
"""


def _errors(rules: list[dict]) -> list[str]:
    return [f"{r.get('id', '?')}: {e}" for r in rules for e in rule_errors(r | {"status": "draft"})]


def _parse(text: str) -> list[dict]:
    m = re.search(r"```(?:ya?ml)?\n(.*?)```", text, re.S)
    doc = yaml.safe_load(m.group(1) if m else text) or {}
    return doc.get("rules", []) if isinstance(doc, dict) else []


def draft(passage: str, school: str, text: str, chapter: str, verse: str | None, edition: str,
          out: Path | None = None) -> tuple[Path, list[str]]:
    """Ask the LLM for rules; validate, retry once with the errors, write to drafts. Returns (path, errors left)."""
    import anthropic
    client = anthropic.Anthropic()
    msgs = [{"role": "user", "content": PROMPT.format(
        school=school, text=text, chapter=chapter, verse=verse or "null", edition=edition,
        domains=", ".join(DOMAINS), dsl=reference(), passage=passage)}]
    for attempt in range(2):
        reply = client.messages.create(model=MODEL, max_tokens=8000, messages=msgs).content[0].text
        rules = [r | {"status": "draft", "school": school} for r in _parse(reply)]
        errs = _errors(rules)
        if not errs:
            break
        msgs += [{"role": "assistant", "content": reply},
                 {"role": "user", "content": "Fix these problems and output the full YAML again:\n" + "\n".join(errs)}]
    out = out or DRAFTS / school / f"{text.split()[0].lower()}_{chapter}_{datetime.now():%Y%m%d%H%M%S}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# Drafted by {MODEL} on {date.today()}; review with `kundli corpus review <id>`.\n"
                   + yaml.safe_dump({"rules": rules}, sort_keys=False, allow_unicode=True, width=110))
    return out, errs


def charts() -> dict[str, Kundli]:
    """Reference charts plus everyone in people/."""
    ins = yaml.safe_load((ROOT / "tests/reference_charts/inputs.yaml").read_text())
    out = {n: BirthData(**b) for n, b in ins.items()}
    for p in sorted((ROOT / "people").glob("*.yaml")):
        out.setdefault(p.stem, BirthData(**yaml.safe_load(p.read_text())["birth"]))
    return {n: Kundli.from_birth(b) for n, b in out.items()}


def random_charts(n: int, seed: int = 0) -> dict[str, Kundli]:
    rng = random.Random(seed)
    out = {}
    for i in range(n):
        dt = datetime(1940, 1, 1) + timedelta(minutes=rng.randrange(80 * 525960))
        b = BirthData(dt_local=dt, tz_name="UTC", lat=round(rng.uniform(-50, 60), 4),
                      lon=round(rng.uniform(-180, 180), 4), time_uncertainty_min=0)
        out[f"random{i}"] = Kundli.from_birth(b)
    return out


def find(rule_id: str) -> Rule:
    for r in load(include_drafts=True):
        if r.id == rule_id:
            return r
    raise KeyError(rule_id)


def review(rule_id: str, search: int = 0) -> tuple[Rule, dict[str, object]]:
    """The rule and its firing on each test chart (plus `search` random charts)."""
    r = find(rule_id)
    ks = charts() | (random_charts(search) if search else {})
    return r, {n: fire(r, k.facts) for n, k in ks.items()}


def verify(rule_id: str, status: str, by: str | None, note: str | None = None) -> None:
    find(rule_id)
    if status == "verified" and not by:
        raise ValueError("verified needs --by")
    ver = verifications()
    ver[rule_id] = {k: v for k, v in {"status": status, "by": by, "date": str(date.today()), "note": note}.items() if v}
    VERIFICATIONS.write_text(yaml.safe_dump(dict(sorted(ver.items())), sort_keys=False, allow_unicode=True))

