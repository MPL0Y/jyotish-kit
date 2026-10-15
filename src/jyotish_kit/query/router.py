"""Question -> topics (and through topics.yaml: houses, karakas, vargas), schools, and a timeframe.

An LLM router with a constrained schema (forced tool call, topic enum) is tried first; its output is
validated, and any failure falls back to the keyword map in topics.yaml. The router never answers.
"""

import re
from datetime import date

from pydantic import BaseModel, Field

from jyotish_kit.synthesis import CONFIG, TOPICS

ROUTER_MODEL = "claude-haiku-4-5-20251001"
TIMING_WORDS = re.compile(r"\b(when|which year|what year|how soon|by when|timing|time window|period|next \d+ years?)\b", re.I)


class Route(BaseModel):
    topics: list[str] = Field(default_factory=list)
    timing: bool = False
    start_year: int | None = None
    end_year: int | None = None
    via: str = "keywords"  # keywords | llm


def _validate(r: Route) -> Route:
    r.topics = [t for t in dict.fromkeys(r.topics) if t in TOPICS]
    return r


def keyword_route(q: str, today: date | None = None) -> Route:
    words = set(re.findall(r"[a-z]+", q.lower()))
    text = " " + " ".join(re.findall(r"[a-z]+", q.lower())) + " "
    topics = [t for t, kws in CONFIG["keywords"].items()
              if any((f" {k} " in text) if " " in k else (k in words) for k in kws)]
    years = sorted(int(y) for y in re.findall(r"\b(19\d\d|20\d\d|21\d\d)\b", q))
    today = today or date.today()
    m = re.search(r"next (\d+) years?", q, re.I)
    start, end = (years[0], years[-1]) if years else (None, None)
    if m:
        start, end = today.year, today.year + int(m.group(1))
    elif re.search(r"\bthis year\b", q, re.I):
        start = end = today.year
    elif re.search(r"\bnext year\b", q, re.I):
        start = end = today.year + 1
    return _validate(Route(topics=topics, timing=bool(TIMING_WORDS.search(q) or start), start_year=start,
                           end_year=end))


TOOL = {
    "name": "route",
    "description": "Classify a Jyotish question into chart topics and an optional timeframe.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topics": {"type": "array", "items": {"type": "string", "enum": list(TOPICS)}, "maxItems": 4,
                       "description": "chart topics the question is about"},
            "timing": {"type": "boolean", "description": "true if the question asks when something happens"},
            "start_year": {"type": ["integer", "null"]},
            "end_year": {"type": ["integer", "null"]},
        },
        "required": ["topics", "timing"],
        "additionalProperties": False,
    },
}


def llm_route(q: str, client=None, today: date | None = None) -> Route:
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    today = today or date.today()
    msg = client.messages.create(
        model=ROUTER_MODEL, max_tokens=300, tools=[TOOL], tool_choice={"type": "tool", "name": "route"},
        messages=[{"role": "user", "content": f"Today is {today}. Topics: " + "; ".join(
            f"{t} ({', '.join(v['domains'])})" for t, v in TOPICS.items()) + f"\n\nQuestion: {q}"}])
    data = next(b.input for b in msg.content if getattr(b, "type", "") == "tool_use")
    return _validate(Route(**data, via="llm"))


def route(q: str, use_llm: bool = True, client=None, today: date | None = None) -> Route:
    if use_llm:
        try:
            r = llm_route(q, client, today)
            if r.topics:
                return r
        except Exception:  # no key, no network, bad output: the keyword map still answers
            pass
    return keyword_route(q, today)
