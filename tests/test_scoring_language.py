from pathlib import Path

import pytest

from app.models import SourceJob
from app.scoring import CandidateEvidence, load_rules, score_job

RULES = load_rules(Path(__file__).parents[1] / "config/scoring.yaml")


def score(description, *, title="AI产品经理", years=0):
    return score_job(SourceJob(source="manual", source_url="https://example.invalid/test",
                              company="虚构语言测试企业", title=title, description=description,
                              locations=["杭州"], employment_type="full_time", employer_kind="large"),
                     CandidateEvidence(skills=["SQL"], full_time_years=years), RULES)


@pytest.mark.parametrize("description", [
    "At least 2 years of professional experience required.",
    "Minimum 4 years work experience.",
    "Must have 2-4 years of full-time experience.",
    "3+ years of experience required.",
    "要求2年以上工作经验。",
])
def test_mandatory_experience(description):
    assert "正式工作年限不满足" in score(description).filter_reasons


@pytest.mark.parametrize("description", [
    "3 years of work experience preferred.",
    "No work experience required.",
    "无需3年工作经验，应届可投。",
    "2年工作经验优先，应届可投。",
])
def test_optional_experience_not_hard_excluded(description):
    assert "正式工作年限不满足" not in score(description).filter_reasons


def test_experience_boundary():
    assert not score("Minimum 3 years of work experience required.", years=3).filtered
    assert score("Minimum 3 years of work experience required.", years=2).filtered


@pytest.mark.parametrize("description", [
    "无需博士学历及以上，应届可投。", "博士学历及以上不需要，应届可投。",
    "PhD not required. Graduate role.",
])
def test_negative_phd(description):
    assert not score(description).filtered


@pytest.mark.parametrize("description", ["博士学历及以上，应届可投。", "PhD required.", "博士优先。"])
def test_positive_phd_still_excluded(description):
    assert score(description).filtered


@pytest.mark.parametrize("description", ["SQL is not required.", "No SQL skills required.", "无需SQL。"])
def test_negative_skill_no_credit(description):
    assert score(description).resume_score == 0


@pytest.mark.parametrize("description", [
    "不要求博士，但需要SQL。", "PhD not required, but SQL required.",
    "无需SQL，但另一工作模块要求SQL。", "不仅需要SQL，还需要沟通能力。",
])
def test_positive_skill_other_clause_preserved(description):
    assert score(description).resume_score == 20


@pytest.mark.parametrize("title", ["Senior AI Product Manager", "artificial intelligence product manager"])
def test_english_role_alias(title):
    assert score("Graduate role.", title=title).expectation_score == 50
