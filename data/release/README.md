# QinghaiRAG release package

This directory contains the five public dataset tables. The latest audited `1.0.0-rc1` build is a real-data benchmark candidate with 868 sources, 653 entities, 1,595 verified facts, 948 release-safe chunks, and 1,000 QA records. Of these, 511 facts and 300 QA records are manually checked.

The candidate meets the configured V1 ranges for sources, QA, and manual review, but it remains below the final V1 entity/fact/chunk scale targets. Do not describe it as the final benchmark-grade release until `python scripts/11_dataset_stats.py` reports that all required V1 ranges are met.

- `qinghai_sources.jsonl`: source registry and release decisions.
- `qinghai_entities.jsonl`: normalized entities and aliases.
- `qinghai_facts.jsonl`: evidence-linked relation triples.
- `qinghai_chunks_open.jsonl`: release-safe open or project-authored synthetic chunks.
- `qinghai_qa_eval.jsonl`: grounded and unanswerable evaluation questions.

Run `python scripts/09_validate_release.py` and `python scripts/11_dataset_stats.py` before every release. Raw HTML, model files, indexes, interim extraction output, statistics reports, and checkpoints are intentionally excluded from Git.
