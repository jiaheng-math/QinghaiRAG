from qinghai_rag.source_discovery import (
    candidate_to_source,
    candidates_from_ihchina_inheritor_payload,
    candidates_from_ihchina_payload,
)


def test_ihchina_catalog_payload_becomes_conservative_source_candidate():
    payload = {
        "list": [
            {
                "id": "14056",
                "num": "Ⅶ-49",
                "auto_id": "348",
                "title": "热贡艺术",
                "type": "传统美术",
                "rx_time": "2006</br>(第一批)",
                "cate": "新增项目",
                "province": "青海省同仁县",
                "protect_unit": "同仁县文化馆",
            }
        ]
    }
    [candidate] = candidates_from_ihchina_payload(payload, discovered_at="2026-07-10")
    assert candidate.source_id == "src_ihchina_14056"
    assert candidate.url == "https://www.ihchina.cn/project_details/14056.html"
    assert candidate.topic == ["非遗", "传统美术"]
    assert candidate.region == ["青海省", "青海省同仁县"]
    assert candidate.catalog_metadata["publication_batch"] == "2006 (第一批)"
    assert candidate.release_policy.value == "metadata_and_facts_only"
    assert candidate.raw_text_release is False

    source = candidate_to_source(candidate)
    assert source.crawl_status.value == "pending"
    assert source.source_id == candidate.source_id


def test_ihchina_catalog_payload_deduplicates_remote_ids():
    item = {"id": "14056", "title": "热贡艺术", "type": "传统美术"}
    records = candidates_from_ihchina_payload({"list": [item, item]})
    assert len(records) == 1


def test_ihchina_inheritor_payload_becomes_conservative_source_candidate():
    payload = {
        "list": [
            {
                "id": "740",
                "num": "01-0025",
                "title": "才让旺堆",
                "day": "1933",
                "sex": "男",
                "nation": "藏族",
                "type": "民间文学",
                "project_num": "Ⅰ-27",
                "project": "格萨(斯)尔",
                "rx_time": "01(2007年（第一批）)",
                "province": "青海省",
                "unit": "青海省",
            }
        ]
    }
    [candidate] = candidates_from_ihchina_inheritor_payload(
        payload, discovered_at="2026-07-10"
    )
    assert candidate.source_id == "src_ihchina_inheritor_740"
    assert candidate.url == "https://www.ihchina.cn/ccr_detail/740.html"
    assert candidate.title == "才让旺堆"
    assert candidate.topic == ["非遗", "代表性传承人", "民间文学"]
    assert candidate.catalog_metadata["project"] == "格萨(斯)尔"
    assert candidate.catalog_metadata["ethnic_group"] == "藏族"
    assert candidate.discovery_method == "ihchina_inheritor_catalog"
    assert candidate.release_policy.value == "metadata_and_facts_only"
