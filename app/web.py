from __future__ import annotations

import json
from html import escape

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from .models import SourceJob, UserStatus
from .scoring import CandidateEvidence
from .service import JobService


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job: dict
    evidence: dict = Field(default_factory=dict)
    mode: str = "link_import"


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[str]


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: UserStatus


def create_app(service: JobService) -> FastAPI:
    app = FastAPI(title="求职 Agent", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/control", response_class=HTMLResponse)
    def control(job_id: int | None = None) -> str:
        resume_block = ""
        if job_id is not None:
            jobs = [item for item in service.list_jobs(include_hidden=True) if item["id"] == job_id]
            if not jobs:
                raise HTTPException(status_code=404, detail="job not found")
            job = jobs[0]
            resume_block = f"""<hr><h2>{escape(job['company'])} · {escape(job['title'])}</h2>
            <p>点击后读取该岗位已生成的、等待确认的简历修改方案。不会覆盖主简历。</p>
            <button onclick=loadProposal()>生成/查看简历方案</button><pre id=proposalResult></pre>
            <script>async function loadProposal(){{let r=await fetch('/api/jobs/{job_id}/resume-proposal');let body=await r.json();document.getElementById('proposalResult').textContent=r.ok?JSON.stringify(body,null,2):(body.detail||'尚未生成方案')}}</script>"""
        return """<!doctype html><meta charset=utf-8><title>求职 Agent</title>
        <style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px}button{padding:10px 18px}</style>
        <h1>求职 Agent 本地控制台</h1><p>更新只检查已配置来源；BOSS、牛客需要浏览器辅助或显式导入。</p>
        <button onclick=run()>更新岗位</button><pre id=result></pre><script>
        async function run(){result.textContent='运行中…';let r=await fetch('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sources:['official_sites','boss','nowcoder']})});result.textContent=JSON.stringify(await r.json(),null,2)}</script>""" + resume_block

    @app.get("/api/jobs/{job_id}/resume-proposal")
    def resume_proposal(job_id: int) -> dict:
        with service.database.connect() as connection:
            row = connection.execute(
                "SELECT id,status,proposal_json,created_at FROM resume_proposals WHERE job_id=? ORDER BY id DESC LIMIT 1",
                (job_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="该岗位尚无简历方案，请先由 Agent 生成")
        return {"proposal_id": row["id"], "status": row["status"], "created_at": row["created_at"], **json.loads(row["proposal_json"])}

    @app.get("/api/jobs")
    def jobs(include_hidden: bool = False) -> list[dict]:
        return service.list_jobs(include_hidden=include_hidden)

    @app.post("/api/import")
    def import_job(request: ImportRequest) -> dict:
        try:
            return service.import_job(
                SourceJob(**request.job), CandidateEvidence(**request.evidence), mode=request.mode
            )
        except (TypeError, ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=escape(str(exc))) from exc

    @app.post("/api/update")
    def update(request: UpdateRequest) -> dict:
        return service.run_update(request.sources)

    @app.post("/api/jobs/{job_id}/status")
    def update_status(job_id: int, request: StatusRequest) -> dict:
        try:
            service.set_user_status(job_id, request.status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        return {"job_id": job_id, "status": request.status}

    return app
