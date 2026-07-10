from qinghai_rag.rag.answer import REFUSAL, EvidenceAnswerer


def test_evidence_answerer_refuses_unsupported_dynamic_intent():
    evidence = [
        {
            "source_id": "src_1",
            "source_url": "https://example.org/a",
            "score": 0.9,
            "text": "塔尔寺酥油花属于传统美术。",
        }
    ]
    result = EvidenceAnswerer().answer("塔尔寺酥油花今年的游客数量是多少？", evidence)
    assert result["refused"] is True
    assert result["answer"] == REFUSAL
