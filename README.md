# QinghaiRAG

QinghaiRAG is a provenance-first dataset package and reproducible RAG/Graph RAG baseline for low-resource Chinese knowledge about Qinghai intangible cultural heritage and regional culture. Ecological tourism is an extension topic, not the first-release scope.

The project is deliberately not marketed as a “Qinghai tourism foundation model.” Its first goal is a small, auditable benchmark in which every released fact, chunk, and answerable QA record resolves to a registered `source_id` and `source_url`.

> **Important:** the committed release is toy data for testing the engineering pipeline. It contains placeholders and fictional organizations and must not be cited as cultural-heritage truth.

## Three release tiers

Scale is a quality gate, not a licence to collect low-quality text. The ordering remains: **source legality > provenance > structure > QA quality > volume**.

| Tier | Sources | Entities | Facts | Open/synthetic chunks | QA | Manual QA | Manual facts |
|---|---:|---:|---:|---:|---:|---:|---:|
| Toy seed | 5–20 | 20–100 | 50–200 | 20–100 | 20–50 | smoke review only | smoke review only |
| v0.1 showcase | 100–300 | 500–1,500 | 2,000–8,000 | 2,000–8,000 | 300–800 | 100–200 | 300–500 |
| v1.0 benchmark | 500–1,500 | 2,000–8,000 | 10,000–50,000 | 10,000–50,000 | 1,000–3,000 | 300–800 | 500–1,000 |

The toy seed is only a smoke test. **v0.1 is the first version appropriate for a CV, GitHub, or Hugging Face showcase; v1.0 is the benchmark-grade target.** The ranges are machine-readable in `configs/scale_targets.yaml`, and the statistics report marks each tier as below/in range/above.

For formal growth, the curation plan is approximately 40% structured facts/triples, 30% project-authored synthetic fact chunks, 20% redistributable official text chunks, and 10% QA/evaluation work. This is a planning mix, not permission to turn restricted prose into synthetic near-copies.

## Why this domain

General-purpose Chinese models and tourism datasets cover popular destinations unevenly. Province-level material about intangible heritage, local organizations, ethnic culture, and administrative regions is fragmented across official sites and often carries different reuse terms. QinghaiRAG turns that problem into a reproducible data-engineering and retrieval benchmark while keeping provenance and copyright decisions visible.

## What is included

| File | Purpose |
|---|---|
| `qinghai_sources.jsonl` | Source registry, retrieval status, licence assessment, and release decision |
| `qinghai_entities.jsonl` | Canonical entities, aliases, regions, and confidence |
| `qinghai_facts.jsonl` | Evidence-linked subject–predicate–object facts |
| `qinghai_chunks_open.jsonl` | Release-safe open text and explicitly labelled project-authored summaries |
| `qinghai_qa_eval.jsonl` | Single-fact, multi-hop, aggregation, comparison, and unanswerable QA |

Raw HTML, cleaned local documents, model weights, FAISS indexes, graphs, and checkpoints are generated locally and excluded from Git.

## Quick start

Python 3.11 or 3.12 is recommended. Python 3.13 support depends on upstream PyTorch/FAISS wheels.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

python scripts/09_validate_release.py
python scripts/11_dataset_stats.py
python scripts/07_build_graph.py
python scripts/06_build_vector_index.py --device cpu
python -m qinghai_rag.rag.evaluate
python scripts/08_run_rag_demo.py
```

The demo defaults to evidence-only answers and never needs an API key. An optional OpenAI-compatible endpoint can be enabled with `OPENAI_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `--use-llm`.

## Reproducible pipeline

```bash
make install
make discover
make init
make collect
make facts
make entities
make chunks
make qa
make index
make graph
make eval
make validate
make stats
```

`make all` runs those data stages in dependency order. Do not run it against third-party sites until seed URLs, reuse terms, robots rules, and contact details have been reviewed.

`make discover` queries the official national ICH catalog for Qinghai project pages and writes a conservative review queue to `data/interim/source_candidates_ihchina.jsonl`. It does not register or crawl candidates. Review the queue first; after approval, run `python scripts/12_discover_ihchina_catalog.py --register`, then collect selected registered source IDs with a real maintainer contact.

The official representative-inheritor directory is a separate source class. Run `python scripts/14_discover_ihchina_inheritors.py` to create its review queue, then add `--register` only after inspecting the candidates. Registration still uses `metadata_and_facts_only` and does not release biography prose.

After collecting reviewed inheritor pages, `python scripts/15_extract_inheritor_facts.py` performs a dry-run exact-field cross-check. Add `--apply` only when `issues` is empty. The extractor uses structured catalog/page fields for project–inheritor, ethnicity, category, applicant, and national-level facts; it intentionally excludes biography prose and conflicting birth-date fields.

`python scripts/16_discover_whlyt_articles.py` discovers articles whose titles match “非遗” in the Qinghai culture-tourism news search. The maintainer confirmed full-text republication permission with attribution: every released chunk records “资料来源：青海省文化和旅游厅官网” and the page URL. Page-level checks still downgrade third-party, signed, explicitly restricted, or missing-source content to `metadata_and_facts_only`. The reviewed HTTPS certificate was expired, so direct collection uses the official HTTP endpoint, records a content hash, and requires `scripts/01_collect_sources.py --no-env-proxy`.

`make qa` targets at least 300 generated records, matching the v0.1 QA floor. If the verified fact graph does not support enough distinct grounded questions, the generator warns and emits fewer records rather than padding the benchmark with duplicates or unsupported questions.

Every derived stage stores an input fingerprint and parameters under `data/cache/checkpoints/`. Re-running with unchanged inputs reuses outputs. Collection checkpoints after every source and raw HTML is written through a temporary file before rename. FAISS also records the chunk fingerprint and embedding model, so an existing index is reused only when compatible.

Use `--no-resume` or the stage-specific `--force` only when an intentional rebuild is needed.

## Collecting real sources

1. Add a page-level record to `configs/sources_seed.yaml`. Prefer a specific official article/table URL over a search or listing page.
2. Record publisher, source type, topic, region, preliminary licence status, and the most conservative plausible release policy.
3. Run `python scripts/00_init_registry.py`.
4. Set a real maintainer contact through `QINGHAI_RAG_CONTACT` or `--contact`, then collect only the reviewed ID:

```bash
python scripts/01_collect_sources.py --source-id src_your_id --contact maintainer@example.org
```

The page is checked again after retrieval. Restricted domains or phrases such as “未经许可不得转载” override permissive seed metadata. Fetch failures are recorded in the registry rather than terminating the batch.

Auto-extracted table facts are marked `verified=false`. Review evidence and normalization before changing them to `verified=true`; only verified medium/high-confidence facts feed synthetic chunks and generated QA.

For sources discovered from the official national ICH catalog, deterministic verification can require exact agreement between the catalog metadata and page-table evidence. Run `python scripts/13_verify_catalog_facts.py` for a dry-run report, then add `--apply` only when the report has no issues. This sets `verified=true` while deliberately leaving `manual_checked=false`; it does not count as human review.

Scanned local-government catalogs use a separate human-review path. Install optional OCR annotation tools with `pip install -e '.[ocr]'`, but treat OCR only as transcription assistance. Store the complete reviewed table, official landing/attachment URLs, review metadata, and attachment SHA-256 under `annotations/local_catalogs/`. Validate the local raw attachment and preview the import before applying it:

```bash
python scripts/18_import_reviewed_local_catalog.py
python scripts/18_import_reviewed_local_catalog.py --apply
```

County-level tourism portals can be expanded conservatively as metadata candidates before any page text is released. For the official Guide County tourism portal, first run a one-page discovery audit, then remove `--max-pages 1` only after checking the candidate metadata:

```bash
python scripts/19_discover_guide_tourism.py --no-env-proxy --max-pages 1
python scripts/19_discover_guide_tourism.py --no-env-proxy
```

Registration is a separate explicit step via `--register`. All discovered Guide pages default to `metadata_and_facts_only`; page-level provenance and reuse checks are still required before collection or release.

After collection, audit cleaned-text quality before treating every fetched page as parsed coverage. The default dry run reports pages below 100 cleaned characters; `--apply` retains their source metadata but changes their crawl status from `parsed` to `fetched`, so image-only and title-only pages do not inflate parsed-source coverage:

```bash
python scripts/20_audit_document_quality.py --source-prefix src_guide_content_
python scripts/20_audit_document_quality.py --source-prefix src_guide_content_ --apply
```

Official Qinghai Tibetan Culture Museum collection objects are discovered from the museum's own structured API. A previously saved list response can be reviewed offline before registration:

```bash
python scripts/21_discover_tibetan_museum_exhibits.py --offline-json /tmp/tibetan_exhibits.json
```

These candidates are classified as museum-official sources but remain `metadata_and_facts_only`; collection images, 3D assets, and curatorial descriptions are not released by default.

The importer is idempotent, refuses a changed attachment hash, marks reviewed facts with `extraction_method=manual_review`, and never releases the scanned PDF as open text.

## Release policy

Publicly accessible does not mean redistributable. The policy engine follows these defaults:

- Explicitly open or reviewed government-public text may enter open chunks with its URL.
- Restricted pages contribute metadata and, when legally appropriate and manually verified, neutral structured facts—not copied prose.
- Unknown terms default to `metadata_and_facts_only` and `raw_text_release=false`.
- Commercial guides, social media, encyclopedias, and unclear scans are excluded unless a maintainer explicitly marks them `local_only`; they never enter the public release automatically.
- Images, audio, and video are not collected or redistributed.

See [SOURCE_POLICY.md](docs/SOURCE_POLICY.md) and always run `make validate` before publishing.

## RAG and Graph RAG baselines

The vector baseline embeds `qinghai_chunks_open.jsonl` with `BAAI/bge-small-zh-v1.5` and stores a FAISS inner-product index plus aligned JSONL metadata. A BM25 sparse baseline (jieba search-mode tokenization, Okapi BM25 built in-memory from the same chunks) runs alongside it. The graph baseline builds a NetworkX multi-directed graph with fact and provenance edges.

Hybrid retrieval fuses dense and BM25 chunk candidates with max-normalized weighted scores (`retrieval.dense_weight`/`retrieval.sparse_weight` in `configs/rag.yaml`), then passes the fused pool plus graph facts through `EvidenceAllocator`, which balances retrieval score, entity overlap, confidence, and source diversity.

An optional cross-encoder reranker (`BAAI/bge-reranker-base` by default, `reranker:` section in `configs/rag.yaml`) rescores candidates before allocation. It is off by default so CPU-only runs stay light; enable it with `--rerank` on the evaluation/demo CLIs or `reranker.enabled: true`. Reranker scores are sigmoid probabilities, so the evidence answerer's minimum-score threshold still applies; the original retrieval score is kept as `retrieval_score`.

The allocator interface is intentionally small so MGEA or learned evidence-budget allocation can replace the heuristic without changing the vector/BM25/graph adapters.

Evaluation reports Recall@k, MRR, evidence hit rate, source diversity, unanswerable refusal rate, and citation presence per mode (`vector-only`, `bm25-only`, `graph-only`, `hybrid`, plus `+rerank` variants when enabled) to `data/interim/eval_report.{json,md}`. The no-LLM baseline evaluates retrieval and refusal only; it does not claim semantic generation quality.

```bash
python -m qinghai_rag.rag.evaluate --top-k 5 --device cuda --rerank
```

Dataset statistics are written to `data/interim/dataset_stats.{json,md}`. They include source/entity/relation/QA distributions, chunk lengths, per-source fact/chunk/QA contributions, tier readiness, and an explicit restricted-source open-text audit. Synthetic summaries may cite restricted sources only when they are genuinely project-authored from publishable verified facts; restricted raw text remains an error.

V1 source coverage is audited separately so a large but narrow registry cannot pass by volume alone:

```bash
python scripts/17_audit_source_coverage.py
```

This writes `data/interim/source_coverage_report.{json,md}` with source-level, topic, prefecture-level region, and region-by-topic coverage plus explicit gaps. Topic targets count only explicit registry labels, so a site brand in a page title cannot create false coverage. Targets and administrative aliases are machine-readable in `configs/coverage_targets.yaml`.

## AutoDL: persistent cache and recovery

Put the repository and all generated state on the AutoDL data disk, not an ephemeral system directory:

```bash
cd /root/autodl-tmp
git clone <your-repository-url> QinghaiRAG
cd QinghaiRAG
bash scripts/autodl_run.sh
```

`scripts/autodl_run.sh` installs the package into the current Python environment, defaults `HF_ENDPOINT` to the hf-mirror for mainland networks, falls back to CPU when CUDA is missing, then runs validate → graph → vector index → evaluation (with reranked modes) → stats, all resume-aware. Tune it with `DEVICE`, `BATCH_SIZE`, `RERANK`, `RUN_DATA_STAGES`, and `SKIP_INSTALL`; the equivalent manual commands are in [AUTODL.md](docs/AUTODL.md).

The code automatically maps Hugging Face, Transformers, Datasets, and Sentence Transformers caches beneath `QINGHAI_RAG_CACHE_DIR/huggingface` unless those environment variables are already set. A restarted job therefore reuses model downloads and only rebuilds an index when its manifest no longer matches.

This release builds indexes; it does **not** fine-tune model parameters. If a later retriever/reranker training stage is added, write optimizer, scheduler, RNG, epoch/step, and best-metric state to `QINGHAI_RAG_CHECKPOINT_DIR`, save atomically at fixed intervals, and expose `--resume-from-checkpoint`. See [AUTODL.md](docs/AUTODL.md).

## Hugging Face export

```bash
make export-hf
# No network push occurs by default.

export HF_TOKEN=...
python scripts/10_export_hf_dataset.py --push --repo-id your-name/QinghaiRAG
```

The exporter creates a `DatasetDict` with `sources`, `entities`, `facts`, `chunks_open`, and `qa_eval` splits. Raw HTML and local-only text are never exported.

## Tests and quality checks

```bash
pytest
ruff check src scripts tests
python scripts/09_validate_release.py
```

Tests cover schemas, conservative release policy, fact extraction, Chinese-aware chunk boundaries, graph/vector retrieval interfaces, and release referential integrity.

## Documentation

- [Dataset card](docs/DATASET_CARD.md)
- [Datasheet](docs/DATASHEET.md)
- [Source policy](docs/SOURCE_POLICY.md)
- [Annotation guide](docs/ANNOTATION_GUIDE.md)
- [RAG report template](docs/RAG_REPORT_TEMPLATE.md)
- [AutoDL runbook](docs/AUTODL.md)

## Roadmap

1. Replace placeholders with reviewed page-level official sources.
2. Reach v0.1: 100–300 sources, 2,000–8,000 facts/chunks, and 300–800 QA with the stated manual-review minimums.
3. ~~Add BM25 + dense hybrid retrieval and a reranker baseline.~~ Done: jieba BM25, weighted dense+sparse fusion, and an optional `bge-reranker-base` cross-encoder.
4. Reach v1.0 across all major Qinghai prefecture-level regions and the planned cultural/tourism topics.
5. Add entity-aware graph expansion, MGEA allocation, ablations, and citation-faithfulness review.
6. Publish only after source-policy and cultural-domain expert review.

Code is Apache-2.0. Dataset records do not inherit the code licence; every source retains its own terms and release decision.
