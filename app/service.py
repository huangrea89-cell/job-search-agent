from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import yaml

from .db import Database
from .models import SourceJob, UserStatus, utc_now
from .official_sources import fetch_official_page
from .pipeline import JobRepository
from .scoring import CandidateEvidence, load_rules, score_job


class JobService:
    def __init__(self, database: Database, scoring_path: Path, sources_path: Path | None = None):
        self.database = database
        self.repository = JobRepository(database)
        self.rules = load_rules(scoring_path)
        self.sources_path = sources_path

    def import_job(self, record: SourceJob, evidence: CandidateEvidence, *, mode: str = "link_import") -> dict:
        job_id, created = self.repository.upsert(record, mode=mode)
        score = score_job(record, evidence, self.rules)
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO job_scores(job_id,expectation_score,resume_score,total_score,stars,confidence,
                filtered,reasons_json,matches_json,gaps_json,needs_confirmation_json,recommendation,rule_version,scored_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET
                expectation_score=excluded.expectation_score,resume_score=excluded.resume_score,
                total_score=excluded.total_score,stars=excluded.stars,confidence=excluded.confidence,
                filtered=excluded.filtered,reasons_json=excluded.reasons_json,matches_json=excluded.matches_json,
                gaps_json=excluded.gaps_json,needs_confirmation_json=excluded.needs_confirmation_json,
                recommendation=excluded.recommendation,rule_version=excluded.rule_version,scored_at=excluded.scored_at""",
                (
                    job_id, score.expectation_score, score.resume_score, score.total_score, score.stars,
                    score.confidence, int(score.filtered), json.dumps(score.filter_reasons, ensure_ascii=False),
                    json.dumps(score.matches, ensure_ascii=False), json.dumps(score.gaps, ensure_ascii=False),
                    json.dumps(score.needs_confirmation, ensure_ascii=False), score.recommendation,
                    score.rule_version, now,
                ),
            )
        return {"job_id": job_id, "created": created, "score": asdict(score)}

    def run_update(self, sources: list[str]) -> dict:
        started = utc_now()
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO update_runs(started_at,status,requested_sources_json) VALUES (?,?,?)",
                (started, "running", json.dumps(sources, ensure_ascii=False)),
            )
            run_id = cursor.lastrowid
        results = {}
        for source in sources:
            if source in {"boss", "nowcoder"}:
                results[source] = {"status": "requires_user_action", "detail": "仅支持浏览器辅助或显式链接/文本导入"}
            elif source == "official_sites":
                urls = []
                if self.sources_path and self.sources_path.exists():
                    with self.sources_path.open(encoding="utf-8") as handle:
                        urls = yaml.safe_load(handle)["sources"]["official_sites"].get("urls", [])
                if not urls:
                    results[source] = {"status": "skipped", "detail": "尚未配置公开官网入口"}
                else:
                    imported = 0
                    failures = []
                    for url in urls:
                        try:
                            for record in fetch_official_page(str(url)):
                                self.import_job(record, CandidateEvidence(), mode="public_fetch")
                                imported += 1
                        except Exception as exc:
                            failures.append({"url": str(url), "error": type(exc).__name__})
                    results[source] = {
                        "status": "completed" if not failures else "partial",
                        "imported": imported,
                        "failures": failures,
                    }
            else:
                results[source] = {"status": "failed", "detail": "未知来源"}
        completed = all(item["status"] == "completed" for item in results.values())
        failed = all(item["status"] == "failed" for item in results.values()) if results else False
        status = "completed" if completed else "failed" if failed else "partial"
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE update_runs SET finished_at=?,status=?,source_results_json=? WHERE id=?",
                (utc_now(), status, json.dumps(results, ensure_ascii=False), run_id),
            )
        return {"run_id": run_id, "status": status, "sources": results}

    def set_user_status(self, job_id: int, status: UserStatus) -> None:
        hidden = int(status in {UserStatus.NOT_INTERESTED, UserStatus.APPLIED})
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET user_status=?,hidden=?,updated_at=? WHERE id=?",
                (status, hidden, utc_now(), job_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(job_id)
            connection.execute(
                "INSERT INTO audit_log(event_type,entity_type,entity_id,details_json,created_at) VALUES (?,?,?,?,?)",
                ("status_changed", "job", str(job_id), json.dumps({"status": status}), utc_now()),
            )

    def list_jobs(self, *, include_hidden: bool = False) -> list[dict]:
        where = "" if include_hidden else "WHERE j.hidden=0"
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""SELECT j.*,s.expectation_score,s.resume_score,s.total_score,s.stars,s.confidence,
                s.filtered,s.reasons_json,s.matches_json,s.gaps_json,s.needs_confirmation_json,s.recommendation,
                (SELECT source_url FROM job_sources js WHERE js.job_id=j.id ORDER BY official DESC,id LIMIT 1) source_url
                FROM jobs j LEFT JOIN job_scores s ON s.job_id=j.id {where}
                ORDER BY COALESCE(s.filtered,1),COALESCE(s.stars,1) DESC,COALESCE(s.total_score,0) DESC,j.first_seen_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]
