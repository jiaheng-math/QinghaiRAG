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

Version `0.1.0` in this repository is a **toy engineering release**. Placeholder URLs, fictional organizations, and example relations test schemas and pipelines. It is not suitable for cultural claims, model comparisons, or production use.

## Splits

- `sources`: source and licence registry.
- `entities`: canonical entities and aliases.
- `facts`: evidence-backed triples.
- `chunks_open`: full-text-compatible or project-authored synthetic retrieval units.
- `qa_eval`: answerable and unanswerable evaluation questions.

## Intended uses

Dataset engineering research, citation-aware retrieval prototypes, Graph RAG interfaces, refusal evaluation, and education about provenance/licensing.

## Out-of-scope uses

Authoritative heritage records, legal or policy advice, commercial travel recommendations, replacing communities/heritage bearers, reconstructing restricted source text, or benchmarking with toy labels.

## Limitations

Coverage is incomplete and source availability can change. Official publication does not eliminate errors or viewpoint bias. Entity aliases can be ambiguous. Automated facts and QA require human review. Text-only release omits multimodal and oral dimensions central to many heritage practices.

## Licensing

Code licensing does not determine dataset licensing. Inspect each `sources` record. Raw/local-only content is excluded. See `docs/SOURCE_POLICY.md`.
