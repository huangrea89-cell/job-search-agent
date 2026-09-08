from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_meta (
  version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  canonical_key TEXT NOT NULL UNIQUE,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  normalized_company TEXT NOT NULL,
  normalized_title TEXT NOT NULL,
  accepted_locations_json TEXT NOT NULL DEFAULT '[]',
  employment_type TEXT NOT NULL DEFAULT 'unknown',
  description TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','unknown','closed')),
  consecutive_missing INTEGER NOT NULL DEFAULT 0 CHECK(consecutive_missing >= 0),
  salary TEXT,
  employer_kind TEXT,
  hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0,1)),
  user_status TEXT NOT NULL DEFAULT 'unprocessed'
    CHECK(user_status IN ('unprocessed','interested','preparing','applied','not_interested')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_sources (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  source_job_id TEXT,
  source_url TEXT NOT NULL,
  official INTEGER NOT NULL DEFAULT 0 CHECK(official IN (0,1)),
  raw_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  UNIQUE(source, source_url)
);
CREATE INDEX IF NOT EXISTS idx_job_sources_job ON job_sources(job_id);
CREATE TABLE IF NOT EXISTS job_scores (
  job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  expectation_score INTEGER NOT NULL CHECK(expectation_score BETWEEN 0 AND 50),
  resume_score INTEGER NOT NULL CHECK(resume_score BETWEEN 0 AND 50),
  total_score INTEGER NOT NULL CHECK(total_score BETWEEN 0 AND 100),
  stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
  confidence TEXT NOT NULL CHECK(confidence IN ('high','medium','low')),
  filtered INTEGER NOT NULL CHECK(filtered IN (0,1)),
  reasons_json TEXT NOT NULL,
  matches_json TEXT NOT NULL,
  gaps_json TEXT NOT NULL,
  needs_confirmation_json TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  rule_version INTEGER NOT NULL,
  scored_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS update_runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running','completed','partial','failed')),
  requested_sources_json TEXT NOT NULL,
  source_results_json TEXT NOT NULL DEFAULT '{}',
  added_count INTEGER NOT NULL DEFAULT 0,
  changed_count INTEGER NOT NULL DEFAULT 0,
  closed_count INTEGER NOT NULL DEFAULT 0,
  filtered_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS resume_versions (
  id INTEGER PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  source_path TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  language TEXT NOT NULL CHECK(language IN ('zh','en')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resume_proposals (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  resume_version_id INTEGER NOT NULL REFERENCES resume_versions(id),
  status TEXT NOT NULL CHECK(status IN ('draft','awaiting_confirmation','approved','rejected','generated')),
  proposal_json TEXT NOT NULL,
  output_path TEXT,
  created_at TEXT NOT NULL,
  confirmed_at TEXT
);
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  resume_proposal_id INTEGER REFERENCES resume_proposals(id),
  status TEXT NOT NULL CHECK(status IN ('preparing','awaiting_user_submit','applied','rejected','interview','offer','withdrawn')),
  applied_at TEXT,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported database schema: {row['version']}")

    def audit(self, event_type: str, entity_type: str, entity_id: str | None, details: dict[str, Any]) -> None:
        from .models import utc_now

        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_log(event_type,entity_type,entity_id,details_json,created_at) VALUES (?,?,?,?,?)",
                (event_type, entity_type, entity_id, json.dumps(details, ensure_ascii=False, sort_keys=True), utc_now()),
            )
