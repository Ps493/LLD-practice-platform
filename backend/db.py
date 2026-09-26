"""SQLite storage. Kept deliberately thin: repositories translate domain
objects <-> rows so the rest of the app never sees SQL. Swapping SQLite for
Postgres later means rewriting this file only.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    id TEXT PRIMARY KEY,
    title TEXT, difficulty TEXT, summary TEXT,
    requirements TEXT, core_entities TEXT, rubric TEXT, tags TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    problem_id TEXT,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    attempt_id TEXT,
    format TEXT,
    content TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id TEXT PRIMARY KEY,
    submission_id TEXT,
    source TEXT,
    score INTEGER,
    strengths TEXT,
    issues TEXT,
    suggestions TEXT,
    notes TEXT,
    created_at TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(reset: bool = False):
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def dumps(x) -> str:
    return json.dumps(x)


def loads(x, default=None):
    if x is None:
        return default
    return json.loads(x)
