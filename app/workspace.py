from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .db import Database


def _decode_json_fields(row: dict) -> dict:
    result = dict(row)
    for key in list(result):
        if key.endswith("_json"):
            result[key.removesuffix("_json")] = json.loads(result.pop(key) or "[]")
    return result


def build_workspace_snapshot(database: Database, output_path: Path, control_url: str) -> Path:
    """Write a non-sensitive, read-only projection of SQLite for workbook generation."""
    with database.connect() as connection:
        jobs = [
            _decode_json_fields(dict(row))
            for row in connection.execute(
                """SELECT j.id,j.company,j.title,j.accepted_locations_json,j.employment_type,j.published_at,
                j.first_seen_at,j.status,j.salary,j.user_status,j.hidden,s.stars,s.total_score,
                s.expectation_score,s.resume_score,s.confidence,s.filtered,s.reasons_json,s.matches_json,
                s.gaps_json,s.needs_confirmation_json,s.recommendation,
                (SELECT p.id FROM resume_proposals p WHERE p.job_id=j.id ORDER BY p.id DESC LIMIT 1) resume_proposal_id,
                (SELECT source_url FROM job_sources js WHERE js.job_id=j.id ORDER BY official DESC,id LIMIT 1) source_url
                FROM jobs j LEFT JOIN job_scores s ON s.job_id=j.id ORDER BY COALESCE(s.stars,1) DESC"""
            ).fetchall()
        ]
        runs = [
            _decode_json_fields(dict(row))
            for row in connection.execute("SELECT * FROM update_runs ORDER BY id DESC").fetchall()
        ]
        applications = [
            dict(row)
            for row in connection.execute(
                """SELECT a.id,j.company,j.title,a.status,a.applied_at,a.notes,a.created_at,a.updated_at,
                r.version resume_version FROM applications a JOIN jobs j ON j.id=a.job_id
                LEFT JOIN resume_proposals p ON p.id=a.resume_proposal_id
                LEFT JOIN resume_versions r ON r.id=p.resume_version_id ORDER BY a.id DESC"""
            ).fetchall()
        ]
    payload = {
        "generated_from": str(database.path),
        "control_url": control_url,
        "jobs": jobs,
        "update_runs": runs,
        "applications": applications,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="workspace-", suffix=".json", dir=output_path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, output_path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return output_path
