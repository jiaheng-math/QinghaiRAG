from pathlib import Path

from qinghai_rag.audit_export import AUDIT_FIELDS, build_audit_samples
from qinghai_rag.schemas import FactRecord, QARecord


def _fact() -> FactRecord:
    return FactRecord(
        fact_id="fact_reviewed",
        subject="测试项目",
        subject_type="ICH_PROJECT",
        predicate="belongs_to_category",
        object="传统技艺",
        object_type="CATEGORY",
        evidence_source_id="src_reviewed",
        evidence_url="https://gov.example/reviewed",
        evidence_text="测试项目；类别：传统技艺",
        extraction_method="manual_review",
        verified=True,
        confidence="high",
        manual_checked=True,
        notes=(
            "manual_review_id=review_fact; reviewed_at=2026-07-10; "
            "reviewer=private@example.com"
        ),
    )


def _qa() -> QARecord:
    return QARecord(
        question_id="q_reviewed",
        question="测试项目属于哪一类别？",
        answer="传统技艺。",
        answer_type="single_fact",
        evidence_fact_ids=["fact_reviewed"],
        evidence_source_ids=["src_reviewed"],
        required_entities=["测试项目", "传统技艺"],
        difficulty="easy",
        manual_checked=True,
        notes=(
            "qa_manual_review_id=review_qa; reviewed_at=2026-07-10; "
            "reviewer=private@example.com"
        ),
    )


def test_build_audit_samples_is_public_and_schema_stable(tmp_path: Path):
    corrections = tmp_path / "corrections.yaml"
    corrections.write_text(
        """
reviewed_at: "2026-07-11"
review_method: Manual correction
records:
  - audit_id: audit_correction_one
    record_type: qa
    record_id: q_old
    record_snapshot: ambiguous question
    review_label: excluded
    error_type: ambiguous_wording
    correction_result: removed
    review_notes: regenerated
    source_ids: []
""".strip(),
        encoding="utf-8",
    )

    samples = build_audit_samples([_fact()], [_qa()], corrections)

    assert len(samples) == 3
    assert all(tuple(item) == AUDIT_FIELDS for item in samples)
    assert {item["review_label"] for item in samples} == {"accepted", "excluded"}
    assert all("private@example.com" not in str(item) for item in samples)
    assert all(len(item["snapshot_sha256"]) == 64 for item in samples)
