from pathlib import Path

import pytest

from qinghai_rag.local_catalogs import (
    ReviewedLocalCatalog,
    build_reviewed_catalog_facts,
    build_reviewed_catalog_source,
    merge_reviewed_catalog_facts,
    verify_reviewed_attachment,
)


def _review(tmp_path: Path) -> tuple[ReviewedLocalCatalog, Path]:
    attachment = tmp_path / "catalog.pdf"
    attachment.write_bytes(b"reviewed catalog")
    review = ReviewedLocalCatalog.model_validate(
        {
            "review_id": "review_test",
            "reviewed_at": "2026-07-10",
            "reviewer_role": "maintainer",
            "review_method": "Visual row review",
            "source_id": "src_local_test",
            "title": "地方非遗名录",
            "publisher": "地方文旅局",
            "parent_page_url": "https://example.gov.cn/notice/1",
            "attachment_url": "https://example.gov.cn/files/1.pdf",
            "attachment_sha256": (
                "6f7fca6ca43ae5940d6d051d0ededd66bb7b9f56b8624c3a55dafe4e5108de9e"
            ),
            "raw_path": "data/raw/local_official/catalog.pdf",
            "region": ["青海省", "西宁市", "湟中区"],
            "topic": ["非遗", "文旅政策", "地方非遗名录"],
            "level": "区级",
            "batch": "第四批",
            "expected_rows": 2,
            "rows": [
                {
                    "sequence": 1,
                    "project_number": "X-1",
                    "project_name": "项目甲",
                    "category": "民俗",
                    "circulation_area": "湟中区",
                },
                {
                    "sequence": 2,
                    "project_number": "Ⅷ-1",
                    "project_name": "项目乙",
                    "category": "传统技艺",
                    "circulation_area": "鲁沙尔镇",
                },
            ],
        }
    )
    return review, attachment


def test_reviewed_catalog_builds_traceable_manual_facts(tmp_path):
    review, attachment = _review(tmp_path)

    assert verify_reviewed_attachment(review, attachment) == review.attachment_sha256
    source = build_reviewed_catalog_source(review)
    facts = build_reviewed_catalog_facts(review)

    assert source.raw_text_release is False
    assert source.content_sha256 == review.attachment_sha256
    assert len(facts) == 6
    assert {fact.predicate for fact in facts} == {
        "belongs_to_category",
        "located_in",
        "has_level",
    }
    assert all(fact.verified and fact.manual_checked for fact in facts)
    assert all(fact.extraction_method == "manual_review" for fact in facts)
    assert all(fact.evidence_source_id == source.source_id for fact in facts)


def test_reviewed_attachment_hash_mismatch_fails(tmp_path):
    review, attachment = _review(tmp_path)
    attachment.write_bytes(b"changed")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_reviewed_attachment(review, attachment)


def test_reviewed_fact_merge_is_idempotent(tmp_path):
    review, _ = _review(tmp_path)
    generated = build_reviewed_catalog_facts(review)

    first, first_report = merge_reviewed_catalog_facts([], generated)
    second, second_report = merge_reviewed_catalog_facts(first, generated)

    assert len(first) == len(second) == 6
    assert first_report["retained_new_facts"] == 6
    assert second_report["retained_new_facts"] == 0
    assert second_report["manual_checked_after"] == 6


def test_reviewed_catalog_rejects_noncontiguous_rows(tmp_path):
    review, _ = _review(tmp_path)
    payload = review.model_dump(mode="json")
    payload["rows"][1]["sequence"] = 3

    with pytest.raises(ValueError, match="contiguous"):
        ReviewedLocalCatalog.model_validate(payload)
