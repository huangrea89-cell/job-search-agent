import json
from pathlib import Path

from app.demo import run_demo


def test_demo_real_scoring_deduplication_and_confirmation(tmp_path):
    output = run_demo(Path(__file__).parents[1], tmp_path)
    result = json.loads((output / "results.json").read_text())
    assert result["input_records"] == 6
    assert result["unique_jobs"] == 5
    assert result["duplicate_created"] is False
    a, b, c, d, e = result["jobs"]
    assert a["total_score"] == 100 and not a["filtered"]
    assert b["total_score"] == a["total_score"] and not b["filtered"]
    assert "2027" in b["needs_confirmation_json"]
    assert c["resume_score"] == 0
    assert d["filtered"] and "工作地点" in d["reasons_json"]
    assert e["filtered"] and "工作年限" in e["reasons_json"]
    assert result["proposal"]["status"] == "awaiting_confirmation"
    snapshot = json.loads((output / "workspace.snapshot.json").read_text())
    assert snapshot["demo"] is True
    assert snapshot["control_url"] == ""
    assert snapshot["generated_from"] == "demo.sqlite3"
    assert len(snapshot["jobs"]) == 5
    assert snapshot["applications"] == []
    assert any(job["resume_proposal_id"] for job in snapshot["jobs"])
    assert run_demo(Path(__file__).parents[1], tmp_path) != output


def test_demo_cli_bypasses_personal_context(tmp_path, monkeypatch, capsys):
    from app import cli
    def forbidden():
        raise AssertionError("demo must not open personal context")
    monkeypatch.setattr(cli, "context", forbidden)
    cli.main(["demo", "--output", str(tmp_path)])
    assert (Path(capsys.readouterr().out.strip()) / "demo.sqlite3").exists()
