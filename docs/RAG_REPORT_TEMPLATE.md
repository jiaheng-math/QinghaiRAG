# QinghaiRAG experiment report

## Experiment identity

- Dataset version / commit:
- Date:
- Embedding model and revision:
- Device / software environment:
- Index/graph manifest fingerprints:
- Retrieval and evidence budgets:

## Dataset statistics

Document source count, entity count, released chunk count, verified/unverified/manually checked fact count, and QA count. State whether the release is toy, v0.1, or v1.0, include the `scale_targets.yaml` assessment, and do not describe an undersized release as benchmark-grade.

| Tier | Sources | Entities | Facts | Chunks | QA | Manual QA | Manual facts |
|---|---:|---:|---:|---:|---:|---:|---:|
| Toy seed | 5–20 | 20–100 | 50–200 | 20–100 | 20–50 | smoke only | smoke only |
| v0.1 | 100–300 | 500–1,500 | 2,000–8,000 | 2,000–8,000 | 300–800 | 100–200 | 300–500 |
| v1.0 | 500–1,500 | 2,000–8,000 | 10,000–50,000 | 10,000–50,000 | 1,000–3,000 | 300–800 | release-specific |

## Source distribution

Break down by publisher, source type, domain, licence status, release policy, region, and topic. Include average facts/chunks/QA links contributed per source and the restricted-source open-text audit.

## Entity distribution

Counts by entity type, confidence, region, and alias count; list unresolved fuzzy matches.

## Fact distribution

Counts by predicate, confidence, verification state, extraction method, and source. Describe conflicts.

## QA type distribution

Counts and difficulty for single fact, multi-hop, regional aggregation, comparison, and unanswerable questions.

## Vector-only results

Report Recall@k, evidence hit rate, source diversity, refusal/citation behavior, latency, and index size.

## Graph-only results

Report the same metrics, hop limit, entity-linking coverage, graph size, and unmatched query entities.

## Hybrid results

Report the same metrics plus allocator budget and ablations for source diversity, overlap, and confidence.

## Failure cases

Provide query, gold evidence, retrieved evidence, failure category, and proposed correction. Separate data, linking, retrieval, allocation, and answer failures.

## Hallucination / refusal analysis

Report unanswerable refusal rate, false refusals, unsupported claims, missing/invalid citations, and human-review protocol.

## Next steps

Prioritize concrete data corrections and ablations. Do not infer benchmark progress from toy data.
