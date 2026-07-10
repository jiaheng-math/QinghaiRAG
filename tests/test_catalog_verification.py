from qinghai_rag.catalog_verification import crosscheck_catalog_facts
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord


def _candidate() -> SourceCandidateRecord:
    return SourceCandidateRecord(
        candidate_id="candidate_1",
        source_id="src_ihchina_1",
        title="热贡艺术",
        publisher="中国非物质文化遗产网",
        source_type="national_official_database",
        url="https://www.ihchina.cn/project_details/1.html",
        domain="ihchina.cn",
        discovery_method="ihchina_catalog",
        discovered_at="2026-07-10",
        catalog_metadata={"category": "传统美术", "applicant": "青海省同仁县"},
    )


def _fact(*, object_value: str = "传统美术") -> FactRecord:
    return FactRecord(
        fact_id="fact_1",
        subject="热贡艺术",
        subject_type="ICH_PROJECT",
        predicate="belongs_to_category",
        object=object_value,
        object_type="CATEGORY",
        evidence_source_id="src_ihchina_1",
        evidence_url="https://www.ihchina.cn/project_details/1.html",
        evidence_text="项目名称：热贡艺术；类别：传统美术",
        extraction_method="table_parse",
        confidence="medium",
    )


def test_exact_catalog_and_page_agreement_can_be_applied_without_manual_flag():
    [verified], report = crosscheck_catalog_facts([_fact()], [_candidate()], apply=True)
    assert report["eligible"] == 1
    assert report["updated"] == 1
    assert report["issues"] == []
    assert verified.verified is True
    assert verified.manual_checked is False
    assert "not manually checked" in verified.notes


def test_catalog_mismatch_remains_unverified_and_is_reported():
    [fact], report = crosscheck_catalog_facts(
        [_fact(object_value="传统技艺")], [_candidate()], apply=True
    )
    assert report["eligible"] == 0
    assert report["updated"] == 0
    assert report["issues"] == [
        {"fact_id": "fact_1", "reasons": ["object_mismatch"]}
    ]
    assert fact.verified is False
