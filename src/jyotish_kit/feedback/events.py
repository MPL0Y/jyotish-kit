"""Life-event log in SQLite (default people/events.db, git-ignored: it is personal data).

people/<name>.yaml `known_life_events` seed it (`import_yaml`, idempotent); `kundli event add` appends.
"""

import sqlite3
from pathlib import Path

import yaml

from jyotish_kit.models import LifeEvent
from jyotish_kit.synthesis import CONFIG, TOPICS

DB = Path(__file__).resolve().parents[3] / "people" / "events.db"
COLS = ("date", "end", "precision", "domain", "description", "polarity")


def connect(db: Path = DB) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY, person TEXT NOT NULL, date TEXT NOT NULL, "end" TEXT, precision TEXT NOT NULL,
        domain TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', polarity INTEGER,
        UNIQUE (person, date, domain, description))""")
    return c


def add(person: str, e: LifeEvent, db: Path = DB) -> bool:
    """True if stored, False if the same event (person, date, domain, description) was already logged."""
    with connect(db) as c:
        cur = c.execute(f'INSERT OR IGNORE INTO events (person, {", ".join(f"{chr(34)}{x}{chr(34)}" for x in COLS)}) '
                        f'VALUES (?{", ?" * len(COLS)})',
                        (person, e.date.isoformat(), e.end.isoformat() if e.end else None, e.precision, e.domain,
                         e.description, e.polarity))
        return cur.rowcount == 1


def events(person: str, db: Path = DB) -> list[LifeEvent]:
    with connect(db) as c:
        rows = c.execute(f'SELECT {", ".join(f"{chr(34)}{x}{chr(34)}" for x in COLS)} FROM events '
                         "WHERE person = ? ORDER BY date", (person,)).fetchall()
    return [LifeEvent(**{k: v for k, v in zip(COLS, r) if v is not None}) for r in rows]


def import_yaml(path: Path, db: Path = DB) -> tuple[str, int]:
    """(person id, number of new events) from people/<name>.yaml."""
    person = path.stem
    evs = yaml.safe_load(path.read_text()).get("known_life_events") or []
    return person, sum(add(person, LifeEvent(**e), db) for e in evs)


def topic_of(domain: str) -> str | None:
    if domain in TOPICS:
        return domain
    if domain in CONFIG["event_domains"]:
        return CONFIG["event_domains"][domain]
    return next((t for t, v in TOPICS.items() if domain in v["domains"]), None)
