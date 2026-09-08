import json
from pathlib import Path

import pytest
import yaml

from app.evaluation import evaluate, main, render_report

ROOT = Path(__file__).parents[1]


def test_reproducible_results_and_denominator():
    result = evaluate(ROOT / "examples/scoring-eval.yaml", ROOT / "config/scoring.yaml")
    assert result == evaluate(ROOT / "examples/scoring-eval.yaml", ROOT / "config/scoring.yaml")
    assert result["total"] == len(result["cases"]) == 12
    assert result["passed"] == 12
    assert result["passed"] == sum(all(row["checks"].values()) for row in result["cases"])
    assert all(row["passed"] == all(row["checks"].values()) for row in result["cases"])
    assert "不是推荐准确率" in render_report(result)
    assert "pending_owner_review" in result["label_status"]


@pytest.mark.parametrize("invalid", ["duplicate", "unknown_check", "empty"])
def test_invalid_fixture_rejected(tmp_path, invalid):
    fixture = yaml.safe_load((ROOT / "examples/scoring-eval.yaml").read_text())
    if invalid == "duplicate":
        fixture["cases"].append(fixture["cases"][0])
    elif invalid == "unknown_check":
        fixture["cases"][0]["expected"] = {"typo": True}
    else:
        fixture["cases"] = []
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(fixture))
    with pytest.raises(ValueError):
        evaluate(path, ROOT / "config/scoring.yaml")


def test_cli_reports_failures_and_strict_exit(tmp_path):
    assert main(["--output", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "results.json").read_text())
    assert main(["--output", str(tmp_path), "--strict"]) == int(result["passed"] < result["total"])


def test_strict_exit_on_unmet_expectation(tmp_path, monkeypatch):
    from app import evaluation
    original = evaluation.evaluate

    def failed(*args):
        result = original(*args)
        result["passed"] -= 1
        result["cases"][0]["passed"] = False
        result["cases"][0]["checks"]["filtered"] = False
        return result

    monkeypatch.setattr(evaluation, "evaluate", failed)
    assert main(["--output", str(tmp_path), "--strict"]) == 1
