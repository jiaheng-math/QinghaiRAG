from qinghai_rag.inheritor_facts import build_inheritor_facts, merge_inheritor_facts
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord


def _candidate(*, ethnic_group: str = "藏族") -> SourceCandidateRecord:
    return SourceCandidateRecord(
        candidate_id="candidate_1",
        source_id="src_ihchina_inheritor_740",
        title="才让旺堆",
        publisher="中国非物质文化遗产网",
        source_type="national_official_database",
        url="https://www.ihchina.cn/ccr_detail/740.html",
        domain="ihchina.cn",
        discovery_method="ihchina_inheritor_catalog",
        discovered_at="2026-07-10",
        catalog_metadata={
            "person": "才让旺堆",
            "project": "格萨(斯)尔",
            "category": "民间文学",
            "applicant": "青海省",
            "project_number": "Ⅰ-27",
            "ethnic_group": ethnic_group,
        },
    )


def _document() -> dict:
    return {
        "source_id": "src_ihchina_inheritor_740",
        "title": "才让旺堆 - 中国非物质文化遗产网",
        "text": (
            "姓名：才让旺堆 民族：藏族 类别：民间文学 项目编号：Ⅰ-27 "
            "项目名称：格萨(斯)尔 申报地区或单位：青海省"
        ),
    }


def test_inheritor_facts_require_catalog_and_page_agreement():
    facts, report = build_inheritor_facts([_candidate()], [_document()])
    assert report["eligible_sources"] == 1
    assert report["issues"] == []
    assert {fact.predicate for fact in facts} == {
        "inherited_by",
        "belongs_to_category",
        "declared_by",
        "has_level",
        "associated_with_ethnic_group",
    }
    assert all(fact.verified and not fact.manual_checked for fact in facts)
    assert all("biography prose was not released" in fact.notes for fact in facts)


def test_empty_ethnic_group_is_skipped_without_rejecting_source():
    candidate = _candidate(ethnic_group="")
    facts, report = build_inheritor_facts([candidate], [_document()])
    assert report["eligible_sources"] == 1
    assert report["skipped_empty_ethnic_group"] == 1
    assert "associated_with_ethnic_group" not in {fact.predicate for fact in facts}


def test_mismatched_page_is_reported_and_generates_no_facts():
    document = _document() | {"text": "不匹配的页面"}
    facts, report = build_inheritor_facts([_candidate()], [document])
    assert facts == []
    assert report["eligible_sources"] == 0
    assert report["issues"]


def test_merge_rebuilds_auto_inheritor_facts_and_keeps_manual_records():
    [generated, *_], _ = build_inheritor_facts([_candidate()], [_document()])
    old_payload = generated.model_dump(mode="json")
    old_payload["fact_id"] = "fact_old"
    old = FactRecord.model_validate(old_payload)
    manual_payload = old.model_dump(mode="json")
    manual_payload.update(fact_id="fact_manual", manual_checked=True)
    manual = FactRecord.model_validate(manual_payload)

    merged, retained = merge_inheritor_facts([old, manual], [generated])

    assert retained == 0
    assert [fact.fact_id for fact in merged] == ["fact_manual"]
