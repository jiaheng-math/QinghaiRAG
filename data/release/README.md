# QinghaiRAG release package

This directory contains the five public dataset tables. The committed records are **toy examples**, not an authoritative Qinghai cultural-heritage dataset. They target the configured toy smoke-test range only; v0.1 is the first public showcase tier and v1.0 is the benchmark tier.

- `qinghai_sources.jsonl`: source registry and release decisions.
- `qinghai_entities.jsonl`: normalized entities and aliases.
- `qinghai_facts.jsonl`: evidence-linked relation triples.
- `qinghai_chunks_open.jsonl`: release-safe open or project-authored synthetic chunks.
- `qinghai_qa_eval.jsonl`: grounded and unanswerable evaluation questions.

Run `python scripts/09_validate_release.py` and `python scripts/11_dataset_stats.py` before every release. Raw HTML, model files, indexes, interim extraction output, statistics reports, and checkpoints are intentionally excluded from Git.
