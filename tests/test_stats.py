from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import ChunkRecord, EntityRecord, FactRecord, QARecord, SourceRecord
from qinghai_rag.stats import _tier_assessment, compute_dataset_stats


def test_current_release_stats_match_records_and_have_no_restricted_open_text():
    sources = read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord)
    entities = read_jsonl(PATHS.release / "qinghai_entities.jsonl", EntityRecord)
    facts = read_jsonl(PATHS.release / "qinghai_facts.jsonl", FactRecord)
    chunks = read_jsonl(PATHS.release / "qinghai_chunks_open.jsonl", ChunkRecord)
    qa = read_jsonl(PATHS.release / "qinghai_qa_eval.jsonl", QARecord)
    stats = compute_dataset_stats(
        sources,
        entities,
        facts,
        chunks,
        qa,
        load_project_config("scale_targets.yaml"),
        load_project_config("release_policy.yaml").get("restricted_domains", []),
    )
    assert stats["restricted_source_chunk_audit"]["passed"] is True
    assert stats["counts"] == {
        "sources": len(sources),
        "entities": len(entities),
        "facts": len(facts),
        "chunks": len(chunks),
        "qa": len(qa),
        "manually_checked_facts": sum(fact.manual_checked for fact in facts),
        "manually_checked_qa": sum(item.manual_checked for item in qa),
    }


def test_scale_assessment_uses_configured_minimums():
    target = load_project_config("scale_targets.yaml")["tiers"]["toy_seed"]
    counts = {
        metric: int(bounds["min"])
        for metric, bounds in target.items()
        if metric != "label"
    }
    assessment = _tier_assessment(counts, target)
    assert assessment["meets_minimum"] is True
    assert all(item["status"] == "in_range" for item in assessment["metrics"].values())

    counts["sources"] -= 1
    assessment = _tier_assessment(counts, target)
    assert assessment["meets_minimum"] is False
    assert assessment["metrics"]["sources"]["status"] == "below"
