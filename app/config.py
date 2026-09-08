from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    database_path: Path
    keychain_service: str


def load_settings(project_root: Path, settings_path: Path | None = None) -> Settings:
    path = settings_path or project_root / "config/settings.yaml"
    if not path.exists():
        path = project_root / "config/settings.example.yaml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    host = str(raw["server"]["host"])
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The MVP server may only bind to a loopback address")
    database_path = Path(raw["database"]["path"])
    if not database_path.is_absolute():
        database_path = project_root / database_path
    return Settings(
        host=host,
        port=int(raw["server"]["port"]),
        database_path=database_path,
        keychain_service=str(raw["models"]["keychain_service"]),
    )


def read_keychain_secret(service: str, account: str) -> str:
    result = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"API Key 未在 macOS 钥匙串服务 {service} 中配置")
    return result.stdout.strip()
