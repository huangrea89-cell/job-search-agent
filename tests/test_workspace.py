import json

from app.db import Database
from app.models import SourceJob
from app.scoring import CandidateEvidence
from app.service import JobService
from app.workspace import build_workspace_snapshot


def test_snapshot_is_read_only_projection_and_contains_no_raw_source(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.migrate()
    service = JobService(db, __import__("pathlib").Path(__file__).parents[1] / "config/scoring.yaml")
    service.import_job(
        SourceJob(
            source="boss", source_url="https://example.com/1", company="示例公司", title="AI 产品经理",
            description="负责AI产品，应届生可投", locations=["上海"], employment_type="full_time",
        ),
        CandidateEvidence(skills=["AI产品"]),
    )
    before = tmp_path.joinpath("db.sqlite3").stat().st_size
    output = build_workspace_snapshot(db, tmp_path / "snapshot.json", "http://127.0.0.1:8765/control")
    payload = json.loads(output.read_text())
    assert payload["jobs"][0]["company"] == "示例公司"
    assert "raw_json" not in payload["jobs"][0]
    assert payload["control_url"].startswith("http://127.0.0.1:")
    assert tmp_path.joinpath("db.sqlite3").stat().st_size == before
