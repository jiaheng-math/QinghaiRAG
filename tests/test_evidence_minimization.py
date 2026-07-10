from qinghai_rag.evidence_minimization import (
    contains_adjacent_personal_field,
    minimize_fact_evidence,
)
from qinghai_rag.schemas import FactRecord


def _fact(fact_id: str, predicate: str, obj: str, evidence_text: str) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        subject="热贡艺术",
        subject_type="ICH_PROJECT",
        predicate=predicate,
        object=obj,
        object_type="CATEGORY" if predicate == "belongs_to_category" else "ORGANIZATION",
        evidence_source_id="src_real_000001",
        evidence_url="https://www.ihchina.cn/project_details/14056.html",
        evidence_text=evidence_text,
        extraction_method="table_parse",
        verified=True,
        confidence="medium",
        manual_checked=True,
        notes="Reviewed.",
    )


def test_minimizes_legacy_table_evidence_without_changing_fact_status():
    category = _fact(
        "fact_category",
        "belongs_to_category",
        "传统美术",
        "姓名：更登达吉；性别：男；出生日期：1964.08；民族：藏族；"
        "类别：传统美术；项目名称：热贡艺术；申报地区或单位：青海省同仁县",
    )
    applicant = _fact(
        "fact_applicant",
        "declared_by",
        "青海省同仁县",
        category.evidence_text,
    )

    updated, report = minimize_fact_evidence([category, applicant])

    assert report["facts_updated"] == 2
    assert report["remaining_personal_field_excerpts"] == 0
    assert report["predicate_distribution"] == {
        "belongs_to_category": 1,
        "declared_by": 1,
    }
    assert updated[0].evidence_text == "项目名称：热贡艺术；类别：传统美术"
    assert updated[1].evidence_text == (
        "项目名称：热贡艺术；申报地区或单位：青海省同仁县"
    )
    assert all(fact.verified and fact.manual_checked for fact in updated)
    assert all(not contains_adjacent_personal_field(fact.evidence_text) for fact in updated)


def test_leaves_already_minimal_evidence_unchanged():
    fact = _fact(
        "fact_minimal",
        "belongs_to_category",
        "传统美术",
        "项目名称：热贡艺术；类别：传统美术",
    )

    updated, report = minimize_fact_evidence([fact])

    assert updated == [fact]
    assert report["facts_updated"] == 0
