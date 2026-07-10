import pytest

from qinghai_rag.tibetan_museum_discovery import (
    candidates_from_tibetan_museum_payload,
)


def test_tibetan_museum_payload_builds_distinct_conservative_exhibit_sources():
    payload = {
        "status": 1,
        "msg": "查询成功",
        "data": {
            "count": 2,
            "list": [
                {
                    "exhibit_id": 4,
                    "exhibit_name": "鎏金银片吐蕃人物像",
                    "museum_id": 1,
                    "museum_name": "青海藏文化博物院",
                    "cate_id": 10,
                    "cate_name": "金银器",
                    "year_name": "吐蕃时期",
                    "texture_name": "银",
                    "three_url": "",
                },
                {
                    "exhibit_id": 5,
                    "exhibit_name": "鎏金银片吐蕃人物像",
                    "museum_id": 1,
                    "museum_name": "青海藏文化博物院",
                    "cate_id": 10,
                    "cate_name": "金银器",
                    "year_name": "吐蕃时期",
                    "texture_name": "银",
                    "three_url": "https://example.org/3d/5",
                },
            ],
        },
    }

    records, metadata = candidates_from_tibetan_museum_payload(payload, discovered_at="2026-07-10")

    assert metadata == {"reported_total": 2, "returned": 2}
    assert len(records) == 2
    assert {record.source_id for record in records} == {
        "src_tibetan_museum_exhibit_4",
        "src_tibetan_museum_exhibit_5",
    }
    assert all(record.source_type.value == "museum_or_scenic_spot_official" for record in records)
    assert all(record.publisher == "青海藏文化博物院" for record in records)
    assert all(record.region == ["青海省", "西宁市"] for record in records)
    assert all("博物馆与文化场馆" in record.topic for record in records)
    assert all("民族文化" in record.topic for record in records)
    assert all(record.release_policy.value == "metadata_and_facts_only" for record in records)
    assert all(record.raw_text_release is False for record in records)
    assert records[0].catalog_metadata["has_3d"] == "false"
    assert records[1].catalog_metadata["has_3d"] == "true"


def test_tibetan_museum_payload_rejects_unsuccessful_status():
    with pytest.raises(ValueError, match="unsuccessful status"):
        candidates_from_tibetan_museum_payload({"status": 0, "msg": "失败"})
