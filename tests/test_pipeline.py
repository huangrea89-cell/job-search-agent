import pytest

from app.db import Database
from app.models import JobStatus, SourceJob
from app.pipeline import JobRepository, accepted_locations, canonical_key, validate_source_mode


def record(**overrides):
    values = dict(
        source="boss",
        source_url="https://www.zhipin.com/job/123#detail",
        company=" 示例 公司 ",
        title="AI 产品经理",
        description="负责 AI 产品",
        locations=["上海市", "北京"],
        employment_type="full_time",
        source_job_id="123",
        official_url="https://careers.example.com/jobs/ai-pm/",
    )
    values.update(overrides)
    return SourceJob(**values)


def test_normalization_keeps_only_accepted_cities():
    assert accepted_locations(["上海/北京", "苏州市", "深圳"]) == ["上海", "苏州"]


def test_official_url_is_canonical_and_preferred(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.migrate()
    repo = JobRepository(db)
    job_id, created = repo.upsert(record())
    assert created
    assert repo.preferred_url(job_id) == "https://careers.example.com/jobs/ai-pm"
    duplicate_id, duplicate_created = repo.upsert(
        record(source="nowcoder", source_url="https://www.nowcoder.com/jobs/456", source_job_id="456")
    )
    assert duplicate_id == job_id
    assert not duplicate_created


def test_missing_requires_two_consecutive_checks(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.migrate()
    repo = JobRepository(db)
    job_id, _ = repo.upsert(record())
    assert repo.mark_missing(job_id) == JobStatus.UNKNOWN
    assert repo.mark_missing(job_id) == JobStatus.CLOSED
    repo.upsert(record())
    with db.connect() as connection:
        row = connection.execute("SELECT status,consecutive_missing FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert tuple(row) == ("open", 0)


def test_browser_sources_reject_unattended_fetch():
    with pytest.raises(PermissionError):
        validate_source_mode("boss", "public_fetch")
    with pytest.raises(PermissionError):
        validate_source_mode("nowcoder", "crawler")


def test_platform_identity_is_stable_without_official_url():
    a = record(official_url=None)
    b = record(official_url=None, company="Renamed company", title="Renamed title")
    assert canonical_key(a) == canonical_key(b)
