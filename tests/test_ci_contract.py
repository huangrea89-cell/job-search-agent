"""Local guardrails for the workflow, not a replacement for Actions execution."""
import re
from pathlib import Path

import yaml


def workflow():
    path = Path(__file__).parents[1] / ".github/workflows/ci.yml"
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def test_ci_permissions_and_pinned_actions():
    ci = workflow()
    assert set(ci["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert ci["permissions"] == {"contents": "read"}
    steps = ci["jobs"]["core"]["steps"]
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
    assert steps[0]["with"]["persist-credentials"] == "false"


def test_ci_runs_strict_evaluation_and_uploads_only_reports():
    core = workflow()["jobs"]["core"]
    assert set(core["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "macos-latest"}
    commands = [step["run"] for step in core["steps"] if "run" in step]
    assert "python -m pip check" in commands
    assert any("pytest" in command for command in commands)
    assert any("app.evaluation" in command and "--strict" in command for command in commands)
    upload = core["steps"][-1]["with"]
    assert set(upload["path"].splitlines()) == {
        "data/ci/junit.xml", "data/ci/evaluation/results.json", "data/ci/evaluation/results.md"}
    assert upload["retention-days"] == "7"
