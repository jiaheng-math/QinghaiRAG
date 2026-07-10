import pytest

from qinghai_rag.tibetan_museum_collection import parse_tibetan_museum_detail


def _payload():
    return {
        "status": 1,
        "msg": "",
        "data": {
            "exhibit_id": 3,
            "exhibit_name": "嵌松石立凤金饰件",
            "museum_name": "青海藏文化博物院",
            "cate_name": "金银器",
            "year_name": "吐蕃时期",
            "texture_name": "金",
            "content": "<p>尺寸：高12.8cm宽9cm</p><p>采用锤揲、镂空等工艺。</p>",
        },
    }


def test_museum_detail_builds_clean_internal_document_text():
    data, text = parse_tibetan_museum_detail(_payload(), expected_exhibit_id="3")

    assert data["exhibit_name"] == "嵌松石立凤金饰件"
    assert "文物名称：嵌松石立凤金饰件" in text
    assert "馆藏机构：青海藏文化博物院" in text
    assert "文物类别：金银器" in text
    assert "年代：吐蕃时期" in text
    assert "质地：金" in text
    assert "馆藏说明：尺寸：高12.8cm宽9cm" in text
    assert "<p>" not in text


def test_museum_detail_rejects_wrong_exhibit_or_owner():
    with pytest.raises(ValueError, match="ID mismatch"):
        parse_tibetan_museum_detail(_payload(), expected_exhibit_id="4")

    payload = _payload()
    payload["data"]["museum_name"] = "其他机构"
    with pytest.raises(ValueError, match="Unexpected museum owner"):
        parse_tibetan_museum_detail(payload, expected_exhibit_id="3")
