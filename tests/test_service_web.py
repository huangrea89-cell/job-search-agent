from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_settings
from app.db import Database
from app.service import JobService
from app.web import create_app

ROOT = Path(__file__).parents[1]


def client(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.migrate()
    return TestClient(create_app(JobService(db, ROOT / "config/scoring.yaml")))


def payload(source="boss"):
    return {
        "job": {
            "source": source,
            "source_url": "https://example.com/job/1",
            "official_url": "https://example.com/job/1",
            "company": "示例公司",
            "title": "AI 产品经理",
            "description": "负责大模型产品，应用经济学专业，应届生可投",
            "locations": ["上海"],
            "employment_type": "full_time",
            "employer_kind": "large",
        },
        "evidence": {"education": ["应用经济学硕士"], "skills": ["大模型产品"]},
    }


def test_loopback_configuration_is_enforced(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("server: {host: 0.0.0.0, port: 1}\ndatabase: {path: x}\nmodels: {keychain_service: x}\n")
    try:
        load_settings(ROOT, path)
    except ValueError as exc:
        assert "loopback" in str(exc)
    else:
        raise AssertionError("non-loopback host accepted")


def test_import_list_and_explicit_status_change(tmp_path):
    web = client(tmp_path)
    response = web.post("/api/import", json=payload())
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert len(web.get("/api/jobs").json()) == 1
    assert web.post(f"/api/jobs/{job_id}/status", json={"status": "not_interested"}).status_code == 200
    assert web.get("/api/jobs").json() == []
    assert len(web.get("/api/jobs?include_hidden=true").json()) == 1


def test_boss_unattended_mode_is_rejected(tmp_path):
    web = client(tmp_path)
    body = payload()
    body["mode"] = "public_fetch"
    response = web.post("/api/import", json=body)
    assert response.status_code == 400


def test_update_isolates_sources_and_reports_user_action(tmp_path):
    web = client(tmp_path)
    result = web.post("/api/update", json={"sources": ["official_sites", "boss", "unknown"]}).json()
    assert result["status"] == "partial"
    assert result["sources"]["boss"]["status"] == "requires_user_action"
    assert result["sources"]["unknown"]["status"] == "failed"


def test_api_forbids_unexpected_fields(tmp_path):
    web = client(tmp_path)
    body = payload()
    body["api_key"] = "must-not-be-accepted"
    assert web.post("/api/import", json=body).status_code == 422


def test_resume_control_is_job_specific_and_safe_without_proposal(tmp_path):
    web = client(tmp_path)
    job_id = web.post("/api/import", json=payload()).json()["job_id"]
    page = web.get(f"/control?job_id={job_id}")
    assert page.status_code == 200
    assert "生成/查看简历方案" in page.text
    assert "不会覆盖主简历" in page.text
    missing = web.get(f"/api/jobs/{job_id}/resume-proposal")
    assert missing.status_code == 404
