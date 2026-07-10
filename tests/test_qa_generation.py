from qinghai_rag.qa_generation import generate_comparison
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
