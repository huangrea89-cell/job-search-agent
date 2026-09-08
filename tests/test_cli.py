import json
from pathlib import Path

import pytest

from app.cli import export_workbook, parser
from app.db import Database


def test_parser_rejects_invalid_user_status():
    with pytest.raises(SystemExit):
        parser().parse_args(["status", "1", "submitted_by_agent"])


def test_export_requires_explicit_artifact_runtime(tmp_path, monkeypatch):
    db = Database(tmp_path / "db.sqlite3")
    db.migrate()
    monkeypatch.delenv("JOB_AGENT_NODE", raising=False)
    monkeypatch.delenv("JOB_AGENT_NODE_MODULES", raising=False)
    monkeypatch.setattr("app.cli.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="artifact-tool"):
        export_workbook(Path(__file__).parents[1], db, "127.0.0.1", 8765, tmp_path / "workspace.xlsx")
    assert (tmp_path / "workspace.snapshot.json").is_file()


def test_example_import_contains_no_credentials():
    payload = json.loads((Path(__file__).parents[1] / "examples/job-import.example.json").read_text())
    assert set(payload) == {"mode", "job", "evidence"}
    assert not ({"api_key", "password", "cookie", "captcha"} & set(payload["job"]))
