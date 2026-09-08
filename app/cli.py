from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import uvicorn

from .config import load_settings, read_keychain_secret
from .db import Database
from .models import SourceJob, UserStatus
from .scoring import CandidateEvidence
from .service import JobService
from .web import create_app
from .workspace import build_workspace_snapshot


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def context():
    root = project_root()
    settings = load_settings(root)
    database = Database(settings.database_path)
    database.migrate()
    service = JobService(database, root / "config/scoring.yaml", root / "config/sources.yaml")
    return root, settings, database, service


def export_workbook(root: Path, database: Database, host: str, port: int, output: Path) -> Path:
    snapshot = output.with_suffix(".snapshot.json")
    build_workspace_snapshot(database, snapshot, f"http://{host}:{port}/control")
    node = os.environ.get("JOB_AGENT_NODE") or shutil.which("node")
    modules = os.environ.get("JOB_AGENT_NODE_MODULES")
    if not node or not modules or not Path(modules).is_dir():
        raise RuntimeError("工作簿导出需要设置 JOB_AGENT_NODE 和 JOB_AGENT_NODE_MODULES（artifact-tool 运行时）")
    with tempfile.TemporaryDirectory(prefix="job-agent-workbook-") as temp:
        temp_path = Path(temp)
        (temp_path / "node_modules").symlink_to(Path(modules), target_is_directory=True)
        builder = temp_path / "build_workspace.mjs"
        shutil.copy2(root / "scripts/build_workspace.mjs", builder)
        result = subprocess.run(
            [node, str(builder), str(snapshot), str(output)], check=False, capture_output=True, text=True
        )
        if result.returncode != 0 or not output.is_file():
            raise RuntimeError(f"工作簿导出失败: {result.stderr.strip() or 'unknown error'}")
    return output


def parser() -> argparse.ArgumentParser:
    root = project_root()
    command = argparse.ArgumentParser(prog="job-agent")
    sub = command.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="初始化 SQLite 数据库")
    demo = sub.add_parser("demo", help="离线运行虚构案例，不读取真实数据库或密钥")
    demo.add_argument("--output", type=Path, default=root / "data/demo-runs")
    serve = sub.add_parser("serve", help="启动回环本地服务")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    import_job = sub.add_parser("import-json", help="显式导入岗位 JSON")
    import_job.add_argument("path", type=Path)
    update = sub.add_parser("update", help="记录一次人工触发的来源更新")
    update.add_argument("sources", nargs="*", default=["official_sites", "boss", "nowcoder"])
    status = sub.add_parser("status", help="更新岗位用户状态")
    status.add_argument("job_id", type=int)
    status.add_argument("value", choices=[item.value for item in UserStatus])
    export = sub.add_parser("export-workspace", help="从 SQLite 导出 Excel 工作台")
    export.add_argument("--output", type=Path, default=root / "data/求职工作台.xlsx")
    sub.add_parser("key-status", help="仅检查 OpenAI Key 是否存在，不显示密钥")
    return command


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if args.command == "demo":
        from .demo import run_demo
        print(run_demo(project_root(), args.output))
        return
    root, settings, database, service = context()
    if args.command == "init":
        print(f"数据库已初始化: {database.path}")
    elif args.command == "serve":
        host = args.host or settings.host
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("服务仅允许绑定回环地址")
        uvicorn.run(create_app(service), host=host, port=args.port or settings.port)
    elif args.command == "import-json":
        payload = json.loads(args.path.read_text(encoding="utf-8"))
        unexpected = set(payload) - {"job", "evidence", "mode"}
        if unexpected:
            raise SystemExit(f"导入文件包含不允许字段: {', '.join(sorted(unexpected))}")
        result = service.import_job(
            SourceJob(**payload["job"]), CandidateEvidence(**payload.get("evidence", {})),
            mode=payload.get("mode", "link_import"),
        )
        print(json.dumps(result, ensure_ascii=False, default=str))
    elif args.command == "update":
        print(json.dumps(service.run_update(args.sources), ensure_ascii=False))
    elif args.command == "status":
        service.set_user_status(args.job_id, UserStatus(args.value))
        print(f"岗位 {args.job_id} 状态已更新为 {args.value}")
    elif args.command == "export-workspace":
        print(export_workbook(root, database, settings.host, settings.port, args.output))
    elif args.command == "key-status":
        try:
            read_keychain_secret(settings.keychain_service, getpass.getuser())
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print("OpenAI API Key 已配置于 macOS 钥匙串")


if __name__ == "__main__":
    main()
