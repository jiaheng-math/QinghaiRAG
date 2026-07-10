import json

from qinghai_rag.io_utils import sha256_bytes
from qinghai_rag.source_discovery import candidate_to_source
from qinghai_rag.tibetan_museum_discovery import tibetan_museum_exhibit_candidate
from qinghai_rag.tibetan_museum_facts import build_tibetan_museum_facts


def _item(exhibit_id: int):
    return {
        "exhibit_id": exhibit_id,
        "exhibit_name": "同名文物",
        "museum_id": 1,
        "museum_name": "青海藏文化博物院",
        "cate_id": 10,
        "cate_name": "金银器",
        "year_name": "吐蕃时期",
        "texture_name": "金",
        "three_url": "",
    }


def _detail(item):
    return {
        "status": 1,
        "msg": "",
        "data": {
            **item,
            "content": "<p>馆藏说明。</p>",
        },
    }


def test_museum_facts_verify_raw_hash_and_disambiguate_same_named_objects(tmp_path):
    candidates = [
        tibetan_museum_exhibit_candidate(_item(4), discovered_at="2026-07-10"),
        tibetan_museum_exhibit_candidate(_item(5), discovered_at="2026-07-10"),
    ]
    sources = []
    for candidate, item in zip(candidates, (_item(4), _item(5))):
        raw = json.dumps(_detail(item), ensure_ascii=False).encode()
        (tmp_path / f"{candidate.source_id}.json").write_bytes(raw)
        source = candidate_to_source(candidate)
        payload = source.model_dump(mode="json")
        payload.update(
            {
                "crawl_status": "parsed",
                "content_sha256": sha256_bytes(raw),
            }
        )
        sources.append(type(source).model_validate(payload))

    facts, report = build_tibetan_museum_facts(candidates, sources, tmp_path)

    assert report["issues"] == []
    assert report["eligible_sources"] == 2
    assert report["generated_facts"] == 8
    assert {fact.subject for fact in facts} == {
        "同名文物（展品ID：4）",
        "同名文物（展品ID：5）",
    }
    assert {fact.predicate for fact in facts} == {
        "belongs_to_category",
        "held_by",
        "created_in_period",
        "made_of",
    }
    assert all(fact.verified and not fact.manual_checked for fact in facts)


def test_museum_facts_report_metadata_mismatch(tmp_path):
    item = _item(4)
    candidate = tibetan_museum_exhibit_candidate(item, discovered_at="2026-07-10")
    detail = _detail(item)
    detail["data"]["texture_name"] = "银"
    raw = json.dumps(detail, ensure_ascii=False).encode()
    (tmp_path / f"{candidate.source_id}.json").write_bytes(raw)
    source = candidate_to_source(candidate)
    payload = source.model_dump(mode="json")
    payload.update({"crawl_status": "parsed", "content_sha256": sha256_bytes(raw)})
    source = type(source).model_validate(payload)

    facts, report = build_tibetan_museum_facts([candidate], [source], tmp_path)

    assert facts == []
    assert report["eligible_sources"] == 0
    assert report["issues"][0]["field"] == "texture"
