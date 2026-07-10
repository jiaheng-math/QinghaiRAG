---
pretty_name: QinghaiRAG
language:
  - zh
tags:
  - retrieval-augmented-generation
  - cultural-heritage
  - knowledge-graph
license: other
---

# QinghaiRAG dataset card

QinghaiRAG packages provenance-aware sources, entities, verified facts, release-safe chunks, and QA evaluation records for Qinghai intangible cultural heritage and regional culture.

## Current status

Version `1.0.0-rc1` is a **real-data benchmark candidate**, built from registered official sources and reviewed local-government attachments. It is no longer the original toy engineering seed.

The latest audited build contains:

| Table or review layer | Records |
|---|---:|
| Registered sources | 868 |
| Canonical entities | 653 |
| Verified facts | 1,595 |
| Release-safe chunks | 948 |
| QA records | 1,000 |
| Manually checked facts | 511 |
| Manually checked QA | 300 |

This candidate meets the configured V1 ranges for sources, QA, manually checked facts, and manually checked QA. It remains below the repository's final V1 targets for entities (2,000), facts (10,000), and chunks (10,000), so it must be described as a release candidate rather than the final benchmark-grade release.

## Configurations

The Hub repository uses configs/subsets because the tables have different schemas. Each config currently exposes a `full` split:

- `source_registry`: source and licence registry.
- `entities`: canonical entities and aliases.
- `facts`: evidence-backed triples.
- `open_chunks`: full-text-compatible or project-authored synthetic retrieval units.
- `qa_benchmark`: answerable and unanswerable evaluation questions.
- `audit_samples`: de-identified accepted review samples and correction records.

For example:

```python
from datasets import load_dataset

facts = load_dataset("jiaheng-math/QinghaiRAG", "facts", split="full")
qa = load_dataset("jiaheng-math/QinghaiRAG", "qa_benchmark", split="full")
audits = load_dataset("jiaheng-math/QinghaiRAG", "audit_samples", split="full")
```

The QA config intentionally remains a single `full` split in this release candidate. A future train/validation/test layout will use entity- and source-aware grouping rather than random row splitting, which would leak near-identical facts across partitions.

## Intended uses

Dataset engineering research, citation-aware retrieval prototypes, Graph RAG interfaces, evidence-retrieval comparisons, refusal evaluation, and education about provenance/licensing.

## Out-of-scope uses

Authoritative heritage records, legal or policy advice, commercial travel recommendations, replacing communities or heritage bearers, reconstructing restricted source text, identifying private individuals, or treating generated QA as an independent measure of world knowledge.

## Provenance and review

Every released fact and answerable QA record resolves to registered `source_id` and `source_url` fields. Current source families include the China Intangible Cultural Heritage website, Qinghai provincial cultural-tourism pages, county-government publications, reviewed official attachments, and the Qinghai Tibetan Culture Museum official API.

`verified=true` means a record passed the pipeline's source and consistency checks. `manual_checked=true` is stricter: a reviewer inspected the exact evidence snapshot. QA approvals are hash-bound, so a regenerated or edited question cannot inherit an earlier manual decision.

The release validator reports zero restricted open-text violations. Open text is included only where the source-level release policy permits it; other sources contribute metadata, reviewed facts, or project-authored synthetic factual summaries.

## Retrieval baselines

The audited 1,000-question run uses `top_k=5`. These are evidence-retrieval metrics, not generative-answer correctness scores.

| Mode | Recall@5 | MRR | Unanswerable refusal | Citation presence |
|---|---:|---:|---:|---:|
| vector-only | 0.9767 | 0.9362 | 1.0000 | 1.0000 |
| bm25-only | 0.9922 | 0.9745 | 1.0000 | 1.0000 |
| graph-only | 0.9978 | 0.9889 | 1.0000 | 1.0000 |
| hybrid | 0.9967 | 0.9881 | 1.0000 | 1.0000 |
| vector-only+rerank | 0.9767 | 0.9579 | 1.0000 | 1.0000 |
| bm25-only+rerank | 0.9922 | 0.9738 | 1.0000 | 1.0000 |
| graph-only+rerank | 0.9978 | 0.9709 | 1.0000 | 1.0000 |
| hybrid+rerank | 1.0000 | 0.9787 | 1.0000 | 1.0000 |

Answerable QA is generated from verified facts and then sampled for manual review. Consequently, these scores measure in-dataset evidence retrieval and should not be presented as performance on unseen external knowledge. Refusal uses a conservative requested-attribute support check: retrieval of a related entity alone is not treated as evidence for an absent field.

## Limitations

Coverage is incomplete and geographically imbalanced, and source availability can change. Official publication does not eliminate errors, historical terminology differences, or institutional viewpoint bias. Entity aliases and short personal names can be ambiguous. Most facts are verified automatically rather than manually checked. Text-only release omits multimodal, spatial, performative, and oral dimensions central to many heritage practices.

## Licensing

Code licensing does not determine dataset licensing, and the dataset repository has no blanket content licence. Inspect each `source_registry` record for `license_status`, `release_policy`, `raw_text_release`, attribution requirements, and the original URL. Raw/local-only and restricted content is excluded. See `docs/SOURCE_POLICY.md`.
