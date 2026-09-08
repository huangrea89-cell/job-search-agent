from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict
from urllib.parse import urlsplit, urlunsplit

from .db import Database
from .models import JobStatus, SourceJob, utc_now

TARGET_CITIES = ("上海", "杭州", "苏州")
BROWSER_ASSISTED_SOURCES = {"boss", "nowcoder"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"[\s·•_|/\\\-—（）()【】\[\]]+", "", value)


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("source_url must be an absolute http(s) URL")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def accepted_locations(locations: list[str]) -> list[str]:
    found = []
    for city in TARGET_CITIES:
        if any(city in location for location in locations):
            found.append(city)
    return found


def canonical_key(record: SourceJob) -> str:
    if record.official_url:
        basis = f"official:{normalize_url(record.official_url)}"
    elif record.source_job_id:
        basis = f"platform:{record.source}:{record.source_job_id.strip()}"
    else:
        cities = ",".join(accepted_locations(record.locations))
        basis = ":".join(
            (normalize_text(record.company), normalize_text(record.title), cities, record.employment_type)
        )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def validate_source_mode(source: str, mode: str) -> None:
    if source in BROWSER_ASSISTED_SOURCES and mode not in {"link_import", "text_import", "browser_assisted"}:
        raise PermissionError(f"{source} only supports explicit import or browser assistance")


class JobRepository:
    def __init__(self, database: Database):
        self.database = database

    def upsert(self, record: SourceJob, *, mode: str = "link_import") -> tuple[int, bool]:
        validate_source_mode(record.source, mode)
        source_url = normalize_url(record.source_url)
        official_url = normalize_url(record.official_url) if record.official_url else None
        key = canonical_key(record)
        now = utc_now()
        locations = accepted_locations(record.locations)
        raw = asdict(record)
        raw["source_url"] = source_url
        with self.database.connect() as connection:
            existing_source = connection.execute(
                "SELECT job_id FROM job_sources WHERE source=? AND source_url=?", (record.source, source_url)
            ).fetchone()
            existing = connection.execute("SELECT id FROM jobs WHERE canonical_key=?", (key,)).fetchone()
            job_id = existing_source["job_id"] if existing_source else (existing["id"] if existing else None)
            created = job_id is None
            if created:
                cursor = connection.execute(
                    """INSERT INTO jobs(canonical_key,company,title,normalized_company,normalized_title,
                    accepted_locations_json,employment_type,description,published_at,first_seen_at,last_seen_at,
                    status,consecutive_missing,salary,employer_kind,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        key, record.company.strip(), record.title.strip(), normalize_text(record.company),
                        normalize_text(record.title), json.dumps(locations, ensure_ascii=False), record.employment_type,
                        record.description.strip(), record.published_at, now, record.fetched_at, JobStatus.OPEN, 0,
                        record.salary, record.employer_kind, now, now,
                    ),
                )
                job_id = cursor.lastrowid
            else:
                connection.execute(
                    """UPDATE jobs SET company=?,title=?,normalized_company=?,normalized_title=?,
                    accepted_locations_json=?,employment_type=?,description=?,published_at=COALESCE(?,published_at),
                    last_seen_at=?,status='open',consecutive_missing=0,salary=COALESCE(?,salary),
                    employer_kind=COALESCE(?,employer_kind),updated_at=? WHERE id=?""",
                    (
                        record.company.strip(), record.title.strip(), normalize_text(record.company),
                        normalize_text(record.title), json.dumps(locations, ensure_ascii=False), record.employment_type,
                        record.description.strip(), record.published_at, record.fetched_at, record.salary,
                        record.employer_kind, now, job_id,
                    ),
                )
            connection.execute(
                """INSERT INTO job_sources(job_id,source,source_job_id,source_url,official,raw_json,fetched_at)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(source,source_url) DO UPDATE SET
                job_id=excluded.job_id,source_job_id=excluded.source_job_id,official=excluded.official,
                raw_json=excluded.raw_json,fetched_at=excluded.fetched_at""",
                (
                    job_id, record.source, record.source_job_id, source_url,
                    int(bool(official_url) and source_url == official_url),
                    json.dumps(raw, ensure_ascii=False, sort_keys=True), record.fetched_at,
                ),
            )
            if official_url and official_url != source_url:
                connection.execute(
                    """INSERT INTO job_sources(job_id,source,source_url,official,raw_json,fetched_at)
                    VALUES (?,?,?,?,?,?) ON CONFLICT(source,source_url) DO UPDATE SET job_id=excluded.job_id,
                    official=1,raw_json=excluded.raw_json,fetched_at=excluded.fetched_at""",
                    (job_id, "official", official_url, 1, json.dumps(raw, ensure_ascii=False), record.fetched_at),
                )
            connection.execute(
                "INSERT INTO audit_log(event_type,entity_type,entity_id,details_json,created_at) VALUES (?,?,?,?,?)",
                ("created" if created else "updated", "job", str(job_id), "{}", now),
            )
        return int(job_id), created

    def mark_missing(self, job_id: int) -> JobStatus:
        now = utc_now()
        with self.database.connect() as connection:
            row = connection.execute("SELECT consecutive_missing FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            missing = row["consecutive_missing"] + 1
            status = JobStatus.CLOSED if missing >= 2 else JobStatus.UNKNOWN
            connection.execute(
                "UPDATE jobs SET consecutive_missing=?,status=?,updated_at=? WHERE id=?",
                (missing, status, now, job_id),
            )
        return status

    def preferred_url(self, job_id: int) -> str:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT source_url FROM job_sources WHERE job_id=? ORDER BY official DESC,id ASC LIMIT 1", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return str(row["source_url"])
