import pytest

from qinghai_rag.qa_generation import (
    generate_comparison,
    generate_regional,
    resolve_qa_minimum,
)
from qinghai_rag.schemas import FactRecord


def _category_fact(fact_id: str, subject: str, category: str) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        subject=subject,
        subject_type="ICH_PROJECT",
        predicate="belongs_to_category",
        object=category,
        object_type="CATEGORY",
        evidence_source_id=f"src_{fact_id}",
        evidence_url=f"https://gov.example/{fact_id}",
        extraction_method="table_parse",
        verified=True,
        confidence="high",
    )


def test_comparison_question_uses_chinese_relation_label():
    facts = [
        _category_fact("1", "土族盘绣", "传统技艺"),
        _category_fact("2", "热贡艺术", "传统美术"),
    ]
    [question] = generate_comparison(facts, target=1)
    assert question.question == "土族盘绣和热贡艺术在当前数据中的类别分别是什么？"
    assert "belongs_to_category" not in question.question


def _declared_fact(fact_id: str, subject: str, applicant: str) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        subject=subject,
        subject_type="ICH_PROJECT",
        predicate="declared_by",
        object=applicant,
        object_type="ORGANIZATION",
        evidence_source_id=f"src_{fact_id}",
        evidence_url=f"https://gov.example/{fact_id}",
        extraction_method="table_parse",
        verified=True,
        confidence="high",
    )


def test_regional_aggregation_uses_administrative_applicants_not_organizations():
    regional = _declared_fact("1", "热贡艺术", "青海省同仁县")
    organization = _declared_fact("2", "藏医药", "青海省某某药业股份有限公司")

    [question] = generate_regional([regional, organization], target=1)

    assert "青海省同仁县" in question.question
    assert "申报" in question.question
    assert question.evidence_fact_ids == [regional.fact_id]


def test_qa_minimum_defaults_to_configured_release_tier():
    targets = {"tiers": {"v0.1": {"qa": {"min": 300}}}}

    assert resolve_qa_minimum(None, targets) == 300
    assert resolve_qa_minimum(1000, targets) == 1000


def test_qa_minimum_rejects_missing_or_nonpositive_values():
    with pytest.raises(ValueError, match="Missing QA minimum"):
        resolve_qa_minimum(None, {})
    with pytest.raises(ValueError, match="must be positive"):
        resolve_qa_minimum(0, {"tiers": {}})
