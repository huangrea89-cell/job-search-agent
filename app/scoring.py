from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Confidence, ScoreResult, SourceJob
from .pipeline import TARGET_CITIES, accepted_locations, normalize_text


@dataclass(slots=True)
class CandidateEvidence:
    education: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    experience_evidence: list[str] = field(default_factory=list)
    transferable_evidence: list[str] = field(default_factory=list)
    full_time_years: int = 0


def load_rules(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        rules = yaml.safe_load(handle)
    if rules["expectation_max"] != 50 or rules["resume_fit_max"] != 50:
        raise ValueError("MVP scoring must retain the confirmed 50/50 split")
    return rules


def _contains_any(text: str, patterns: list[str] | tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(pattern) in normalized for pattern in patterns)


def _positive_clauses(text: str) -> list[str]:
    """Exclude explicit non-requirements, bounded by punctuation/contrast.

    This is a conservative lexical rule, not general negation understanding.
    Keep other clauses so '不要求博士，但需要SQL' still matches SQL.
    """
    clauses = re.split(r"[，,；;。\n!?！？]|\.(?:\s|$)|\bbut\b|但是|但", text, flags=re.I)
    negative = r"不(?:需要|要求|必具备)|无需|无须|不必|\bnot\s+(?:required|necessary)\b|\bno\s+.+?\s+(?:required|necessary)\b|\b(?:do|does)\s+not\s+require\b"
    return [clause for clause in clauses if not re.search(negative, clause, re.I)]


def _hard_filters(job: SourceJob, evidence: CandidateEvidence, rules: dict) -> tuple[list[str], list[str]]:
    text = f"{job.title}\n{job.description}"
    positive = "\n".join(_positive_clauses(text))
    reasons: list[str] = []
    needs: list[str] = []

    if job.employment_type not in {"full_time", "unknown"}:
        reasons.append("非全职岗位")
    elif job.employment_type == "unknown":
        needs.append("工作形式待确认")

    locations = accepted_locations(job.locations)
    if job.locations and not locations:
        reasons.append("工作地点不在目标城市")
    elif not job.locations:
        needs.append("工作地点待确认")

    if re.search(r"博士(?:学历)?(?:及以上|以上|要求|必须)|ph\.?d\.?\s*(?:required|minimum)", positive, re.I):
        reasons.append("明确要求博士")
    elif re.search(r"博士优先|ph\.?d\.?\s*preferred", positive, re.I):
        reasons.append("博士优先")

    required_years = []
    for clause in _positive_clauses(text):
        # Preferred experience is not a mandatory minimum.
        if re.search(r"优先|加分|\bpreferred\b|\bnice to have\b", clause, re.I):
            continue
        required_years.extend(int(year) for year in re.findall(r"(?:至少|需|要求)?\s*(\d+)\s*年(?:以上)?(?:全职|工作)?经验", clause))
        english = re.search(r"(?<![\d.])(\d+)\s*(?:[-–]\s*\d+\s*)?\+?\s*years?\s+(?:of\s+)?(?:(?:full[- ]time|work|professional)\s+)?experience", clause, re.I)
        if english and re.search(r"\brequired\b|\bminimum\b|\bat least\b|\bmust\b", clause, re.I):
            required_years.append(int(english.group(1)))
    if required_years and min(required_years) >= rules["hard_filters"]["reject_required_full_time_years_at_least"]:
        if evidence.full_time_years < min(required_years):
            reasons.append("正式工作年限不满足")
    elif not re.search(r"经验不限|应届|校招|毕业生", text):
        needs.append("工作年限待确认")

    if _contains_any(job.title, ["销售", "客户经理", "商务拓展", "BD"]):
        reasons.append("销售岗位")
    project_terms = ("进度管理", "交付管理", "资源协调", "项目排期")
    product_terms = ("产品定义", "需求设计", "产品决策", "用户研究")
    if "项目经理" in job.title and _contains_any(text, project_terms) and not _contains_any(text, product_terms):
        reasons.append("纯项目管理岗位")

    excluded_kinds = set(rules["hard_filters"]["excluded_company_kinds"])
    if job.employer_kind in excluded_kinds:
        reasons.append(f"排除的公司类型:{job.employer_kind}")
    elif not job.employer_kind:
        needs.append("公司规模待确认")

    graduation_years = set(
        re.findall(r"(?:毕业(?:时间|年份)|(?:仅限|面向))\s*[:：]?\s*(20\d{2})", text)
    )
    explicitly_27_only = (
        ("2027" in graduation_years and "2026" not in graduation_years)
        or ("27届" in text and "26届" not in text)
    )
    if explicitly_27_only and not re.search(r"往届(?:可投|可申请|不限)|接受往届", text):
        needs.append("校招资格不符合：岗位要求2027届/2027年毕业，候选人2026年6月毕业")
    elif "27届" in text and not re.search(r"26届|2026\s*年\s*毕业|往届", text):
        needs.append("校招资格待确认")

    return list(dict.fromkeys(reasons)), list(dict.fromkeys(needs))


def _evidence_matches(text: str, items: list[str]) -> list[str]:
    matches = []
    normalized = normalize_text("\n".join(_positive_clauses(text)))
    for item in items:
        tokens = [token for token in re.split(r"[,，、;/；\s]+", item) if len(normalize_text(token)) >= 2]
        compact = normalize_text(item)
        for suffix in ("硕士研究生", "硕士", "本科", "学士"):
            if compact.endswith(suffix) and len(compact) > len(suffix):
                tokens.append(compact[: -len(suffix)])
        if any(normalize_text(token) in normalized for token in tokens):
            matches.append(item)
    return matches


def score_job(job: SourceJob, evidence: CandidateEvidence, rules: dict) -> ScoreResult:
    reasons, needs = _hard_filters(job, evidence, rules)
    text = f"{job.title}\n{job.description}"
    weights = rules["expectation_weights"]
    expectation = 0
    if _contains_any(text, rules["target_role_terms"]):
        expectation += weights["target_direction"]
    if accepted_locations(job.locations):
        expectation += weights["target_city"]
    if job.employment_type == "full_time":
        expectation += weights["full_time"]
    if job.employer_kind in {"large", "state_owned", "foreign", "listed"}:
        expectation += weights["company_preference"]

    direct = _evidence_matches(text, evidence.skills + evidence.experience_evidence)
    education = _evidence_matches(text, evidence.education)
    transferable = _evidence_matches(text, evidence.transferable_evidence)
    resume_weights = rules["resume_fit_weights"]
    resume = 0
    if direct:
        resume += min(resume_weights["direct_evidence"], 10 + 10 * len(direct))
    if education:
        resume += resume_weights["education_relevance"]
    if transferable:
        resume += resume_weights["transferable_evidence"]

    total = min(100, expectation + resume)
    thresholds = {int(stars): value for stars, value in rules["star_thresholds"].items()}
    stars = next((stars for stars in (5, 4, 3, 2) if total >= thresholds[stars]), 1)
    confidence = Confidence.HIGH if not needs and job.official_url else Confidence.MEDIUM if len(needs) <= 2 else Confidence.LOW
    filtered = bool(reasons) or total < thresholds[2]
    if reasons:
        stars = 1
    matches = direct + education + transferable
    gaps = [] if direct else ["岗位核心要求暂无可追溯候选人证据"]
    recommendation = "不进入主推荐表" if filtered else "建议优先评估" if stars >= 4 else "建议用户判断后决定"
    return ScoreResult(
        filtered=filtered,
        filter_reasons=reasons or (["内部总分低于40"] if total < 40 else []),
        expectation_score=expectation,
        resume_score=resume,
        total_score=total,
        stars=stars,
        confidence=confidence,
        needs_confirmation=needs,
        recommendation=recommendation,
        matches=matches,
        gaps=gaps,
        rule_version=int(rules["version"]),
    )
