from qinghai_rag.qa_manual_review import (
    QAManualReviewDecision,
    apply_qa_manual_review,
    build_batch_decisions,
    prepare_review_batch,
    qa_sha256,
    select_review_sample,
)
from qinghai_rag.schemas import QARecord


def _qa(index: int, answer_type: str = "single_fact", manual_checked: bool = False) -> QARecord:
    unanswerable = answer_type == "unanswerable"
    return QARecord(
        question_id=f"q_{index:03d}",
        question=f"问题 {index}？",
        answer="当前数据集中没有足够依据回答。" if unanswerable else f"答案 {index}。",
        answer_type=answer_type,
        evidence_fact_ids=[] if unanswerable else [f"fact_{index:03d}"],
        evidence_source_ids=[] if unanswerable else [f"src_{index:03d}"],
        required_entities=[f"实体 {index}"],
        unanswerable=unanswerable,
        manual_checked=manual_checked,
    )


def _qa_set() -> list[QARecord]:
    records = []
    index = 0
    for answer_type, count in {
        "single_fact": 40,
        "regional_aggregation": 20,
        "multi_hop": 20,
        "comparison": 10,
        "unanswerable": 10,
    }.items():
        for _ in range(count):
            records.append(_qa(index, answer_type))
            index += 1
    return records


def test_select_review_sample_is_deterministic_and_stratified():
    qa = _qa_set()
    first = select_review_sample(qa, 30, "review_test")
    second = select_review_sample(list(reversed(qa)), 30, "review_test")
    assert [item.question_id for item in first] == [item.question_id for item in second]
    assert {kind: sum(item.answer_type == kind for item in first) for kind in {
        "single_fact", "regional_aggregation", "multi_hop", "comparison", "unanswerable"
    }} == {
        "single_fact": 12,
        "regional_aggregation": 6,
        "multi_hop": 6,
        "comparison": 3,
        "unanswerable": 3,
    }


def test_prepare_review_batch_resumes_from_decisions():
    qa = _qa_set()
    selected = select_review_sample(qa, 30, "review_test")
    decisions = build_batch_decisions(selected[:10], "review_test", "batch_001", "reviewer")
    batch, status = prepare_review_batch(qa, decisions, "review_test", 30, 10)
    assert len(batch) == 10
    assert status["accepted"] == 10
    assert status["batch_id"] == "batch_002"
    assert not ({item.question_id for item in batch} & {item.question_id for item in selected[:10]})


def test_apply_qa_review_requires_minimum_and_exact_snapshot():
    qa = [_qa(1), _qa(2)]
    decisions = build_batch_decisions(qa, "review_test", "batch_001", "reviewer")
    updated, report = apply_qa_manual_review(qa, decisions, "review_test", 2)
    assert report["issues"] == []
    assert report["new_manual_checks"] == 2
    assert all(item.manual_checked for item in updated)
    assert qa_sha256(updated[0]) == qa_sha256(qa[0])

    stale = decisions[0].model_copy(update={"qa_sha256": "0" * 64})
    unchanged, report = apply_qa_manual_review(qa, [stale, decisions[1]], "review_test", 2)
    assert any(issue["issue"] == "qa_snapshot_changed" for issue in report["issues"])
    assert not any(item.manual_checked for item in unchanged)


def test_decision_schema_rejects_invalid_date():
    item = _qa(1)
    payload = build_batch_decisions([item], "review_test", "batch_001", "reviewer")[0]
    assert QAManualReviewDecision.model_validate(payload).reviewed_at
