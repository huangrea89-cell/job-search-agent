from pathlib import Path

from app.models import Confidence, SourceJob
from app.scoring import CandidateEvidence, load_rules, score_job

RULES = load_rules(Path(__file__).parents[1] / "config/scoring.yaml")


def job(**overrides):
    values = dict(
        source="official",
        source_url="https://example.com/job/1",
        official_url="https://example.com/job/1",
        company="示例大厂",
        title="AI 产品经理",
        description="负责大模型产品定义与用户研究，要求应用经济学或相关专业，应届生可投",
        locations=["上海"],
        employment_type="full_time",
        employer_kind="large",
    )
    values.update(overrides)
    return SourceJob(**values)


def evidence():
    return CandidateEvidence(
        education=["应用经济学硕士"],
        skills=["用户研究", "大模型产品"],
        experience_evidence=["完成用户研究并形成产品建议"],
        transferable_evidence=["数据分析"],
        full_time_years=0,
    )


def test_high_match_is_explainable_and_not_filtered():
    result = score_job(job(), evidence(), RULES)
    assert result.expectation_score == 50
    assert result.resume_score >= 40
    assert result.stars == 5
    assert not result.filtered
    assert result.matches
    assert result.confidence == Confidence.HIGH


def test_missing_fields_reduce_confidence_not_core_score():
    complete = score_job(job(), evidence(), RULES)
    incomplete = score_job(job(locations=[], employment_type="unknown", employer_kind=None), evidence(), RULES)
    assert incomplete.resume_score == complete.resume_score
    assert incomplete.confidence == Confidence.LOW
    assert "工作地点待确认" in incomplete.needs_confirmation


def test_phd_preferred_is_hard_filtered():
    result = score_job(job(description="博士优先，负责大模型产品"), evidence(), RULES)
    assert result.filtered and result.stars == 1
    assert "博士优先" in result.filter_reasons


def test_required_work_years_do_not_count_internship():
    result = score_job(job(description="要求1年以上工作经验，负责大模型产品"), evidence(), RULES)
    assert "正式工作年限不满足" in result.filter_reasons


def test_project_manager_product_role_is_not_title_filtered():
    result = score_job(job(title="AI 项目经理", description="负责产品定义、需求设计和产品决策"), evidence(), RULES)
    assert "纯项目管理岗位" not in result.filter_reasons


def test_non_target_city_is_filtered():
    result = score_job(job(locations=["北京"]), evidence(), RULES)
    assert "工作地点不在目标城市" in result.filter_reasons


def test_2026_application_deadline_does_not_mask_2027_graduation_annotation():
    result = score_job(
        job(description="校招。毕业时间：2027年；招聘截止日期：2026.10.31。负责大模型产品。"),
        evidence(),
        RULES,
    )
    assert "校招资格不符合：岗位要求2027届/2027年毕业，候选人2026年6月毕业" in result.needs_confirmation
    assert "校招毕业时间不符合" not in result.filter_reasons
    assert not result.filtered and result.stars >= 2


def test_explicit_alumni_eligibility_keeps_2027_posting():
    result = score_job(
        job(description="27届校招，往届可申请，负责大模型产品和用户研究。"),
        evidence(),
        RULES,
    )
    assert "校招毕业时间不符合" not in result.filter_reasons
