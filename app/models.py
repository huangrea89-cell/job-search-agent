from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStatus(StrEnum):
    OPEN = "open"
    UNKNOWN = "unknown"
    CLOSED = "closed"


class UserStatus(StrEnum):
    UNPROCESSED = "unprocessed"
    INTERESTED = "interested"
    PREPARING = "preparing"
    APPLIED = "applied"
    NOT_INTERESTED = "not_interested"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(slots=True)
class SourceJob:
    source: str
    source_url: str
    company: str
    title: str
    description: str
    locations: list[str]
    employment_type: str = "unknown"
    source_job_id: str | None = None
    official_url: str | None = None
    published_at: str | None = None
    salary: str | None = None
    employer_kind: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ScoreResult:
    filtered: bool
    filter_reasons: list[str]
    expectation_score: int
    resume_score: int
    total_score: int
    stars: int
    confidence: Confidence
    needs_confirmation: list[str]
    recommendation: str
    matches: list[str]
    gaps: list[str]
    rule_version: int
