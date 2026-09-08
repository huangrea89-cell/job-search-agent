import sqlite3

import pytest

from app.db import Database


def test_migrate_is_idempotent_and_enables_foreign_keys(tmp_path):
    db = Database(tmp_path / "jobs.sqlite3")
    db.migrate()
    db.migrate()
    with db.connect() as connection:
        assert connection.execute("SELECT version FROM schema_meta").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_database_rejects_invalid_states(tmp_path):
    db = Database(tmp_path / "jobs.sqlite3")
    db.migrate()
    with pytest.raises(sqlite3.IntegrityError), db.connect() as connection:
        connection.execute(
            """INSERT INTO jobs(canonical_key,company,title,normalized_company,normalized_title,
            first_seen_at,last_seen_at,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("key", "公司", "岗位", "公司", "岗位", "now", "now", "invented", "now", "now"),
        )


def test_audit_log_serializes_without_ascii_escaping(tmp_path):
    db = Database(tmp_path / "jobs.sqlite3")
    db.migrate()
    db.audit("created", "job", "1", {"reason": "用户导入"})
    with db.connect() as connection:
        payload = connection.execute("SELECT details_json FROM audit_log").fetchone()[0]
    assert "用户导入" in payload
