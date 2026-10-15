"""Layer 2 data: the rule corpus.

Rule files live at corpus/<school>/*.yaml, each a mapping {defaults: {...}, rules: [...]}; the defaults
are deep-merged into every rule of that file. Review state is kept apart in corpus/verifications.yaml
(id -> status, by, date, note), so verifying a rule is a one-line diff and rule files stay as authored.
Drafts from the ingestion tool are written to corpus/drafts/<school>/ and never fire unless asked for.
"""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel

from jyotish_kit.dsl.evaluator import SCHOOLS, DSLError, check, check_predicates, evaluate
from jyotish_kit.facts.builders.vargas import VARGAS
from jyotish_kit.facts.graph import FactGraph
from jyotish_kit.models import Rule

CORPUS = Path(__file__).parent
SCHEMA_PATH = CORPUS / "schema.json"
VERIFICATIONS = CORPUS / "verifications.yaml"
DRAFTS = CORPUS / "drafts"


def schema() -> dict:
    return Rule.model_json_schema()


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def rule_files(include_drafts: bool = False) -> list[Path]:
    files = sorted(p for s in SCHOOLS for p in (CORPUS / s).glob("*.yaml"))
    return files + (sorted(DRAFTS.rglob("*.yaml")) if include_drafts else [])


def raw_rules(files: list[Path]) -> list[tuple[Path, dict]]:
    out = []
    for f in files:
        doc = yaml.safe_load(f.read_text()) or {}
        if not isinstance(doc, dict) or not isinstance(doc.get("rules"), list):
            raise ValueError(f"{f}: expected a mapping with a `rules` list")
        out += [(f, _merge(doc.get("defaults", {}), r)) for r in doc["rules"]]
    return out


def verifications() -> dict[str, dict]:
    return (yaml.safe_load(VERIFICATIONS.read_text()) or {}) if VERIFICATIONS.exists() else {}


def load(include_drafts: bool = False) -> list[Rule]:
    """All rules, with review status applied from verifications.yaml."""
    ver = verifications()
    rules = []
    for _, d in raw_rules(rule_files(include_drafts)):
        v = ver.get(d.get("id"), {})
        if v:
            d = d | {"status": v["status"], "verified_by": v.get("by")}
        rules.append(Rule.model_validate(d))
    return rules


def validate(include_drafts: bool = True) -> list[str]:
    """Every problem in the corpus: schema, ids, citations, school/directory, DSL names and arity."""
    errs = []
    sch = schema()
    if not SCHEMA_PATH.exists() or json.loads(SCHEMA_PATH.read_text()) != sch:
        errs.append(f"{SCHEMA_PATH.name} is out of date with the Rule model (run `kundli corpus schema`)")
    validator = Draft202012Validator(sch)
    errs += check_predicates()
    seen: dict[str, Path] = {}
    try:
        items = raw_rules(rule_files(include_drafts))
    except (ValueError, yaml.YAMLError) as e:
        return errs + [str(e)]
    for path, d in items:
        rid = d.get("id", "<no id>")
        where = f"{path.relative_to(CORPUS)}: {rid}"
        errs += [f"{where}: {e}" for e in rule_errors(d, validator)]
        if rid in seen:
            errs.append(f"{where}: duplicate id (also in {seen[rid].relative_to(CORPUS)})")
        seen[rid] = path
        if path.parent.name in SCHOOLS and d.get("school") != path.parent.name:
            errs.append(f"{where}: school {d.get('school')!r} but file is under {path.parent.name}/")
    for rid, v in verifications().items():
        if rid not in seen:
            errs.append(f"verifications.yaml: unknown rule {rid}")
        elif v.get("status") == "verified" and not v.get("by"):
            errs.append(f"verifications.yaml: {rid}: verified without `by`")
    return errs


def rule_errors(d: dict, validator: Draft202012Validator | None = None) -> list[str]:
    """Problems in one merged rule dict: schema, varga, DSL names and arity."""
    validator = validator or Draft202012Validator(schema())
    errs = [f"{'/'.join(map(str, e.path)) or '(rule)'}: {e.message}"
            for e in sorted(validator.iter_errors(d), key=lambda e: list(e.path))]
    if d.get("varga", "D1") not in (*VARGAS, "KP"):
        errs.append(f"unknown varga {d.get('varga')!r}")
    if any(c in str(d.get("name", "")) for c in "[]"):
        errs.append("name: square brackets are reserved for citations in narration")
    for field, timing in (("condition", False), ("cancels_if", False), ("timing", True)):
        if isinstance(d.get(field), str):
            errs += [f"{field}: {e}" for e in check(d[field], d.get("school") or "common", allow_timing=timing)]
    return errs


class Firing(BaseModel):
    """One rule evaluated against one chart: whether its condition held, and on which facts."""
    rule_id: str
    school: str
    fired: bool  # condition true and not cancelled
    condition: bool
    matched: list[str]
    cancelled: bool = False
    cancelled_by: list[str] = []
    error: str | None = None


def fire(rule: Rule, facts: FactGraph) -> Firing:
    try:
        ok, ids = evaluate(rule.condition, facts, rule.varga, rule.school)
        cancelled, cids = False, []
        if ok and rule.cancels_if:
            cancelled, cids = evaluate(rule.cancels_if, facts, rule.varga, rule.school)
        return Firing(rule_id=rule.id, school=rule.school, fired=bool(ok and not cancelled), condition=bool(ok),
                      matched=ids, cancelled=bool(cancelled), cancelled_by=cids if cancelled else [])
    except DSLError as e:
        return Firing(rule_id=rule.id, school=rule.school, fired=False, condition=False, matched=[], error=str(e))


def timing_active(rule: Rule, facts: FactGraph, lords: dict[str, str]) -> tuple[bool, list[str]]:
    """Whether the rule's timing expression holds for the running dasha lords
    (dasha_lord, antardasha_lord, pratyantardasha_lord)."""
    if not rule.timing:
        return False, []
    v, ids = evaluate(rule.timing, facts, rule.varga, rule.school, timing=lords)
    return bool(v), ids
