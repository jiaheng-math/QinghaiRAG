from __future__ import annotations

import pytest
from pydantic import ValidationError

from qinghai_rag.schemas import QARecord, SourceRecord


def source(**updates):
    payload = {
        "source_id": "src_test",
        "title": "测试",
        "publisher": "测试机构",
        "source_type": "other",
        "url": "https://example.org/a",
        "domain": "example.org",
        "retrieved_at": "2026-07-10",
        "license_status": "unclear",
        "release_policy": "metadata_and_facts_only",
        "raw_text_release": False,
        "crawl_status": "pending",
    }
    payload.update(updates)
    return SourceRecord.model_validate(payload)


def test_source_schema_accepts_conservative_record():
    assert source().province == "青海省"


def test_source_schema_rejects_raw_release_under_metadata_policy():
    with pytest.raises(ValidationError):
        source(raw_text_release=True)


def test_answerable_qa_requires_evidence():
    with pytest.raises(ValidationError):
        QARecord(
            question_id="q_test",
            question="问题？",
            answer="答案。",
            answer_type="single_fact",
            evidence_fact_ids=[],
            evidence_source_ids=[],
            required_entities=[],
        )
