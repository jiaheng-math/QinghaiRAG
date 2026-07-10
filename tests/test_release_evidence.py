from qinghai_rag.config import PATHS
from qinghai_rag.evidence_minimization import contains_adjacent_personal_field
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import FactRecord


def test_release_fact_evidence_has_no_unrelated_personal_fields():
    facts = read_jsonl(PATHS.release / "qinghai_facts.jsonl", FactRecord)

    assert all(not contains_adjacent_personal_field(fact.evidence_text) for fact in facts)
