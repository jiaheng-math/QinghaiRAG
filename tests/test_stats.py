from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import ChunkRecord, EntityRecord, FactRecord, QARecord, SourceRecord
from qinghai_rag.stats import compute_dataset_stats


def test_toy_release_meets_smoke_scale_and_has_no_restricted_open_text():
    stats = compute_dataset_stats(
        read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord),
        read_jsonl(PATHS.release / "qinghai_entities.jsonl", EntityRecord),
        read_jsonl(PATHS.release / "qinghai_facts.jsonl", FactRecord),
        read_jsonl(PATHS.release / "qinghai_chunks_open.jsonl", ChunkRecord),
        read_jsonl(PATHS.release / "qinghai_qa_eval.jsonl", QARecord),
        load_project_config("scale_targets.yaml"),
        load_project_config("release_policy.yaml").get("restricted_domains", []),
    )
    assert stats["scale_assessment"]["toy_seed"]["meets_minimum"] is True
    assert stats["scale_assessment"]["v0.1"]["meets_minimum"] is False
    assert stats["restricted_source_chunk_audit"]["passed"] is True
    assert stats["counts"] == {
        "sources": 5,
        "entities": 23,
        "facts": 50,
        "chunks": 20,
        "qa": 20,
        "manually_checked_facts": 0,
        "manually_checked_qa": 0,
    }
