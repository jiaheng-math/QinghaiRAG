from qinghai_rag.rag.answer import REFUSAL, EvidenceAnswerer


def _evidence(text: str) -> list[dict]:
    return [
        {
            "source_id": "src_1",
            "source_url": "https://example.org/a",
            "score": 0.9,
            "text": text,
        }
    ]


def test_evidence_answerer_refuses_unsupported_dynamic_intent():
    result = EvidenceAnswerer().answer(
        "塔尔寺酥油花今年的游客数量是多少？",
        _evidence("塔尔寺酥油花属于传统美术。"),
    )
    assert result["refused"] is True
    assert result["answer"] == REFUSAL


def test_evidence_answerer_refuses_unsupported_benchmark_attributes():
    questions = [
        "官磨药香最近一次保护评估的具体得分是多少？",
        "藏族唐卡最近一次保护评估的具体日期是什么？",
        "一真天然真香古法制作技艺当前执行的保护规划文号是什么？",
        "嵌宝石金鹅饰件的具体出土地点是什么？",
        "陶质单把壶的入藏日期是哪一天？",
        "青海湖周边地区女子服饰的文物定级是什么？",
        "玉马最近一次修复的日期是什么？",
        "尼玛最近一次公开传习活动是什么时候？",
    ]

    for question in questions:
        result = EvidenceAnswerer().answer(question, _evidence("仅记录类别、年代和来源。"))
        assert result["refused"] is True, question


def test_evidence_answerer_accepts_evidence_that_contains_requested_attribute():
    result = EvidenceAnswerer().answer(
        "某项目最近一次保护评估的具体日期是什么？",
        _evidence("某项目最近一次保护评估日期为2025年6月1日。"),
    )

    assert result["refused"] is False
