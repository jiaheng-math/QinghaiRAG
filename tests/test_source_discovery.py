from qinghai_rag.source_discovery import (
    candidate_to_source,
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
