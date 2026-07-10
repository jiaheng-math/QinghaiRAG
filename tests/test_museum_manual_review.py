from qinghai_rag.museum_manual_review import (
    MuseumManualReview,
    mark_museum_manual_review,
)
from qinghai_rag.schemas import FactRecord, SourceRecord


def _source() -> SourceRecord:
    return SourceRecord(
        source_id="src_tibetan_museum_exhibit_3",
        title="嵌松石立凤金饰件",
        publisher="青海藏文化博物院",
        source_type="museum_or_scenic_spot_official",
        url="https://museum.example/detail?exhibit_id=3",
        domain="museum.example",
        retrieved_at="2026-07-10",
        release_policy="metadata_and_facts_only",
        crawl_status="parsed",
        content_sha256="a" * 64,
    )


def _facts():
    relations = {
        "belongs_to_category": ("金银器", "CATEGORY"),
        "created_in_period": ("吐蕃时期", "HISTORICAL_PERIOD"),
        "held_by": ("青海藏文化博物院", "ORGANIZATION"),
        "made_of": ("金", "MATERIAL"),
    }
    return [
        FactRecord(
            fact_id=f"fact_{predicate}",
            subject="嵌松石立凤金饰件",
            subject_type="MUSEUM_OBJECT",
            predicate=predicate,
            object=obj,
            object_type=object_type,
            evidence_source_id="src_tibetan_museum_exhibit_3",
            evidence_url="https://museum.example/detail?exhibit_id=3",
            extraction_method="rule",
            verified=True,
            confidence="high",
        )
        for predicate, (obj, object_type) in relations.items()
    ]


def _review() -> MuseumManualReview:
    return MuseumManualReview.model_validate(
        {
            "review_id": "review_test",
            "reviewed_at": "2026-07-10",
            "reviewer_role": "maintainer",
            "review_method": "Field review",
            "expected_sources": 1,
            "expected_facts": 4,
            "rows": [
                {
                    "source_id": "src_tibetan_museum_exhibit_3",
                    "exhibit_id": 3,
                    "name": "嵌松石立凤金饰件",
                    "category": "金银器",
                    "period": "吐蕃时期",
                    "museum": "青海藏文化博物院",
                    "material": "金",
                }
            ],
        }
    )


def test_museum_manual_review_marks_exact_four_fact_set():
    updated, report = mark_museum_manual_review(_facts(), [_source()], _review())

    assert report["issues"] == []
    assert report["matched_facts"] == 4
    assert report["new_manual_checks"] == 4
    assert report["manual_checked_after"] == 4
    assert all(fact.manual_checked for fact in updated)
    assert all("source_content_sha256=" in fact.notes for fact in updated)


def test_museum_manual_review_refuses_mismatched_relation():
    facts = _facts()
    payload = facts[0].model_dump(mode="json")
    payload["object"] = "错误类别"
    facts[0] = FactRecord.model_validate(payload)

    updated, report = mark_museum_manual_review(facts, [_source()], _review())

    assert report["issues"][0]["issue"] == "fact_set_mismatch"
    assert report["matched_facts"] == 0
    assert all(not fact.manual_checked for fact in updated)
