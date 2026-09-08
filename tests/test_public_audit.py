import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("public_audit", Path(__file__).parents[1] / "scripts/audit_public_history.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_scanner_reports_types_without_values():
    secret = "sk-" + "x" * 25
    result = audit.scan(secret.encode())
    assert result == ["api_key_shape"]
    assert secret not in str(result)


def test_binary_is_not_claimed_clean():
    assert audit.scan(b"\x89PNG\0test") == ["binary_manual_review"]


def test_regular_example_is_clean():
    assert audit.scan(b"https://example.invalid/jobs/1") == []
