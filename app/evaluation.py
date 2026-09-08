"""Offline challenge evaluation; labels are not a human-validated gold set."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import yaml

from .models import SourceJob
from .scoring import CandidateEvidence, load_rules, score_job

CHECKS = {"filtered", "needs_contains", "reasons_contains", "resume_score_max", "expectation_score_min"}


def evaluate(fixture_path: Path, rules_path: Path) -> dict:
    fixture = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    ids = [case["id"] for case in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("Evaluation requires nonempty cases with unique IDs")
    rules = load_rules(rules_path)
    rows = []
    for case in cases:
        expected = case["expected"]
        if not expected or set(expected) - CHECKS:
            raise ValueError(f"Unsupported or empty expectations: {case['id']}")
        result = score_job(SourceJob(**(fixture["base_job"] | case["job"])),
                           CandidateEvidence(**case.get("candidate", fixture["candidate"])), rules)
        actual = asdict(result)
        checks = {}
        for key, value in expected.items():
            if key == "filtered":
                checks[key] = actual[key] == value
            elif key.endswith("_contains"):
                field = "needs_confirmation" if key == "needs_contains" else "filter_reasons"
                checks[key] = any(value in item for item in actual[field])
            elif key == "resume_score_max":
                checks[key] = actual["resume_score"] <= value
            else:
                checks[key] = actual["expectation_score"] >= value
        rows.append({"id": case["id"], "category": case["category"], "intent": case["intent"],
                     "expected": expected, "actual": actual, "checks": checks, "passed": all(checks.values())})
    return {"label_status": fixture["label_status"], "rule_version": rules["version"],
            "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            "rules_sha256": hashlib.sha256(rules_path.read_bytes()).hexdigest(),
            "scorer_sha256": hashlib.sha256(Path(__file__).with_name("scoring.py").read_bytes()).hexdigest(),
            "total": len(rows), "passed": sum(row["passed"] for row in rows), "cases": rows}


def render_report(result: dict) -> str:
    lines = ["# 评分挑战集结果", "", "合成案例；AI 拟定预期，待项目作者复核。不是盲测、独立人工金标集或真实招聘样本。",
             "", f"案例级通过：{result['passed']}/{result['total']}。一例中所有声明的检查均通过才算通过；该比例不是推荐准确率或录用概率。",
             "", "| ID | 类别 | 预期行为 | 结果 | 未通过检查 |", "| --- | --- | --- | --- | --- |"]
    for row in result["cases"]:
        failed = "、".join(key for key, ok in row["checks"].items() if not ok) or "—"
        lines.append(f"| {row['id']} | {row['category']} | {row['intent']} | {'通过' if row['passed'] else '未通过'} | {failed} |")
    lines += ["", "完整实际输出与输入/规则/实现的 SHA-256 见同目录 results.json。",
              "", f"评分规则版本：{result['rule_version']}。本报告保留全部输入案例；历史结果请参阅基线记录。"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true", help="Any unmet expectation exits with status 1")
    args = parser.parse_args(argv)
    result = evaluate(root / "examples/scoring-eval.yaml", root / "config/scoring.yaml")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "results.md").write_text(render_report(result), encoding="utf-8")
    print(f"Cases passed: {result['passed']}/{result['total']}; labels pending owner review")
    return int(args.strict and result["passed"] != result["total"])


if __name__ == "__main__":
    raise SystemExit(main())
