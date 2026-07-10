# QinghaiRAG: A Provenance-First Dataset and Reproducible RAG/Graph RAG Baseline for Qinghai Cultural Heritage

**Technical Report — Version 1.0.0-rc1**  
**Snapshot date:** 2026-07-11  
**Dataset status:** real-data release candidate; not yet the final benchmark-grade V1 release  
**Code:** [github.com/jiaheng-math/QinghaiRAG](https://github.com/jiaheng-math/QinghaiRAG)  
**Dataset repository:** [huggingface.co/datasets/zhangjh123/QinghaiRAG](https://huggingface.co/datasets/zhangjh123/QinghaiRAG) (planned public RC publication)

## Abstract

QinghaiRAG is a Chinese-language dataset and reproducible retrieval baseline for Qinghai intangible cultural heritage and regional culture. The project starts from a practical difficulty: evidence about Qinghai heritage is scattered across national catalogs, provincial and county government pages, local official attachments, and museum systems, and these materials carry very different reuse permissions and risks. QinghaiRAG builds provenance, release policy, evidence traceability, refusal behavior, and human review into the pipeline itself, instead of appending them as documentation after the fact.

The audited `1.0.0-rc1` snapshot contains 868 registered sources, 653 canonical entities, 1,595 verified facts, 948 release-safe chunks, and 1,000 evaluation questions. A maintainer manually checked 511 facts and 300 hash-bound QA snapshots. The public tables carry stable source and evidence identifiers; raw pages, local attachments, model files, and indexes stay out of the dataset release. The release validator reports zero restricted open-text violations.

Four retrieval families are evaluated at `top_k=5` — dense vector retrieval, BM25, graph retrieval, and hybrid retrieval — each with and without a BGE cross-encoder reranker. On the current in-dataset evidence benchmark, hybrid retrieval with reranking reaches Recall@5 of 1.0000, while graph-only retrieval yields the best MRR at 0.9889. After an explicit requested-attribute support check was added, all eight modes reach an unanswerable refusal rate and citation-presence rate of 1.0000. These numbers measure evidence retrieval over QA generated from the same verified fact universe; they say nothing about open-domain factual generalization or generative answer quality.

The snapshot is labeled a candidate for two reasons. It meets the configured V1 ranges for sources, QA, manually checked facts, and manually checked QA, but remains below the targets of 2,000 entities, 10,000 facts, and 10,000 chunks. Separately, a public-release audit still has to finish stripping adjacent personal fields that may linger in some structured evidence excerpts. This report documents both gaps.

## 1. Motivation and Scope

### 1.1 Motivation

Information about Qinghai cultural heritage is fragmented across institutions and publication systems. National intangible-cultural-heritage catalogs hold structured project and representative-inheritor records. Provincial and county portals publish notices, policies, event reports, tourism information, and downloadable lists. Museums expose collection metadata through web applications and structured APIs. All of this is useful for retrieval-augmented generation; none of it can safely be collapsed into a single unrestricted text corpus.

QinghaiRAG addresses four needs:

1. **Traceable evidence.** Every public fact and answerable QA item should resolve to a registered source and URL.
2. **Policy-aware release.** Public accessibility is not blanket permission to redistribute prose, images, audio, or video.
3. **Comparable retrieval baselines.** Vector, lexical, graph, hybrid, and reranked retrieval should run against the same public evidence package.
4. **Observable quality control.** Manual approvals, rejected QA designs, source failures, policy downgrades, and coverage gaps should remain visible.

QinghaiRAG is a dataset-engineering and evidence-retrieval benchmark. It is not a “Qinghai tourism foundation model,” an authoritative heritage registry, or a substitute for the communities, heritage bearers, museums, and government institutions whose records it draws on.

### 1.2 Domain scope

The first release centers on:

- Qinghai intangible cultural heritage projects;
- public representative inheritors, with only the minimum fields needed for project relations;
- administrative applicants, regions, categories, levels, and ethnic-group relations;
- reviewed county-level heritage inventories;
- selected Qinghai Tibetan Culture Museum object metadata;
- redistributable provincial cultural-tourism text with source attribution.

Ecological tourism, scenic sites, policy documents, and broader regional culture are extension areas. The source coverage audit shows that ecological tourism and cultural-tourism policy still sit below their configured targets, so the release makes no claim of comprehensive coverage there.

### 1.3 Release tiers and current status

QinghaiRAG defines three machine-readable scale tiers in `configs/scale_targets.yaml`.

| Tier | Sources | Entities | Facts | Chunks | QA | Manual QA | Manual facts |
|---|---:|---:|---:|---:|---:|---:|---:|
| Toy seed | 5–20 | 20–100 | 50–200 | 20–100 | 20–50 | smoke only | smoke only |
| v0.1 showcase | 100–300 | 500–1,500 | 2,000–8,000 | 2,000–8,000 | 300–800 | 100–200 | 300–500 |
| v1.0 benchmark | 500–1,500 | 2,000–8,000 | 10,000–50,000 | 10,000–50,000 | 1,000–3,000 | 300–800 | 500–1,000 |
| **Current RC** | **868** | **653** | **1,595** | **948** | **1,000** | **300** | **511** |

The current release meets four of the seven V1 dimensions and misses three: entities, facts, and chunks. The `1.0.0-rc1` label reflects design and pipeline readiness; the remaining scale gates are still open.

## 2. Source Governance

### 2.1 Source families

The source registry spans five operational source families:

| Source family | Registered records | Parsed records | Primary contribution |
|---|---:|---:|---|
| National ICH project and inheritor pages | 192 | 192 | project, category, applicant, level, inheritor, ethnicity |
| Qinghai provincial culture-tourism articles | 159 | 126 | attributed public text and policy/event context |
| Reviewed local-government catalogs | 6 | 6 | manually checked local projects, regions, levels, inheritors |
| Guide County tourism portal | 327 | 292 | county-level source coverage and internal documents |
| Qinghai Tibetan Culture Museum objects | 184 | 184 | object category, period, material, holding institution |
| **Total** | **868** | **800** | — |

The 68 records that did not reach parsed status stay visible in the registry: 33 provincial `/content` pages returned server errors, and 35 Guide County pages were downgraded from `parsed` to `fetched` because their cleaned text ran under 100 characters. The registry covers six unique publishers and five unique domains.

Representative upstream systems include the [China Intangible Cultural Heritage website](https://www.ihchina.cn/), the [Qinghai Department of Culture and Tourism](http://whlyt.qinghai.gov.cn/), the [Guide County Government tourism portal](https://www.guide.gov.cn/gdly), the [Huangzhong District Government](https://www.huangzhong.gov.cn/), and the [Qinghai Tibetan Culture Museum](https://www.tibetanculturemuseum.com.cn/pcweb/).

### 2.2 Release policy classes

Each source record carries a `license_status`, `release_policy`, a `raw_text_release` decision, retrieval date, content hash when available, and notes. The policy classes are:

- `full_text_allowed`: explicit open terms or documented permission allows redistribution;
- `government_public`: reviewed government-public prose may be released with provenance;
- `short_excerpt_only`: only a necessary reviewed excerpt may be retained;
- `metadata_and_facts_only`: public metadata and conservative facts may be released, not copied prose;
- `local_only`: material supports private analysis but is excluded from public data;
- `exclude`: the source is not collected into the release.

When reuse terms are unknown, the defaults are `metadata_and_facts_only`, `license_status=unclear`, and `raw_text_release=false`. Strong page phrases such as “未经许可不得转载,” restricted domains, third-party bylines, and page-specific limitations override permissive seed metadata. Government ownership does not by itself license the redistribution of every embedded asset or quotation.

### 2.3 Text, attachments, and media

Raw HTML and API JSON are retained only under ignored local storage. Reviewed PDF, DOCX, or HTML attachments stay local and appear publicly only through source metadata, SHA-256 values, reviewed transcriptions, and structured facts. Images, audio, video, 3D models, and museum collection media are excluded by default.

The provincial culture-tourism text path is the one maintainer-authorized exception: eligible official pages use the `government_public` policy, and every released chunk keeps the source URL and the attribution “资料来源：青海省文化和旅游厅官网.” Third-party, signed, restricted, or missing-source pages are downgraded after fetch. Of 126 successfully parsed pages, 122 contribute open text and four were conservatively downgraded.

### 2.4 Coverage audit

Coverage is computed only from sources with `crawl_status=parsed`, using explicit source type, topic, and region metadata; a keyword in a title does not count as topic coverage.

All four source-level targets are met: national official, provincial official, municipal/county official, and museum/scenic official. Every prefecture-level region target is met except Haibei Tibetan Autonomous Prefecture, which has 8 parsed sources against a target of 10. Two topic gaps remain:

| Topic | Current | Minimum | Gap |
|---|---:|---:|---:|
| Ecological tourism | 42 | 50 | 8 |
| Cultural-tourism policy | 10 | 50 | 40 |

Until these close, the registry is large but thematically uneven; the release does not claim balanced province-wide coverage.

## 3. Data Schema

### 3.1 Public Hugging Face configurations

The Hugging Face layout uses heterogeneous configs — the tables genuinely are different kinds of data, not train/test splits of one corpus:

- `source_registry`
- `entities`
- `facts`
- `open_chunks`
- `qa_benchmark`
- `audit_samples`

Each config currently exposes a `full` split. Canonical JSONL copies, SHA-256 values, reports, and the relevant pipeline configs ship alongside the Hub-native Parquet representation. `RELEASE_MANIFEST.json` binds the exported tables to their row counts and checksums.

### 3.2 Source registry

`source_registry` is the policy and provenance root. Key fields include `source_id`, title, publisher, source type, URL/domain, language, region/topic labels, retrieval date, license status, release policy, `raw_text_release`, crawl status, content SHA-256, and notes. No downstream record may cite an unregistered source.

### 3.3 Entities and aliases

The entity table holds stable IDs, canonical names, types, aliases, descriptions, region metadata, canonical source IDs, and confidence. The schema covers ICH projects, regions, categories, people, organizations, ethnic groups, scenic spots, festivals/events, museum objects, materials, historical periods, and concepts.

The current build contains 653 canonical entities and 30 alias mappings. Alias normalization handles punctuation and reviewed spelling variants, but fuzzy matching never confers authority on its own. Homonyms and short personal names remain a limitation.

### 3.4 Evidence-backed facts

Facts use a subject–predicate–object representation with subject/object types, evidence source ID, source URL, a short evidence excerpt when release-safe, extraction method, verification status, confidence, manual-review flag, and notes. Supported relations include project category, region, applicant, protection organization, representative inheritor, ethnic group, festival, level, museum holding institution, period, and material.

The 1,595 facts break down as follows:

| Origin | Facts | Verification path |
|---|---:|---|
| National ICH project pages | 132 | structured extraction plus catalog/page checks; 14 manually checked |
| National representative-inheritor pages | 273 | exact catalog/detail-field agreement |
| Reviewed local-government catalogs | 457 | complete human row review and attachment hashing |
| Museum object API | 733 | deterministic list/detail agreement; 40 manually checked |
| **Total** | **1,595** | **511 manually checked** |

### 3.5 Release-safe chunks

The release contains 948 retrieval chunks:

- 353 attributed `open_text` chunks from permitted provincial pages;
- 595 `synthetic_fact` chunks written by the project from verified structured relations.

Synthetic chunks are labeled as generated summaries and keep their source IDs and URLs; they are never presented as official prose. Chunking uses bounded character offsets with overlap. A cursor bug that once spun dozens of near-duplicate tail chunks out of short documents was fixed before this snapshot (Section 8.2).

### 3.6 QA and audit samples

The QA table contains 1,000 records across single-fact, multi-hop, comparison, regional-aggregation, and unanswerable types. Each answerable record points to its evidence facts and source IDs. The benchmark includes 100 unanswerable items; Recall@5 and MRR are computed over the 900 answerable ones.

The `audit_samples` config holds de-identified accepted fact/QA review snapshots and correction records — 814 rows in the expected RC package: 511 accepted fact audits, 300 accepted QA audits, and three documented QA corrections. Reviewer email addresses and local paths are not exported.

## 4. Fact Extraction and Validation

### 4.1 Structured extraction

HTML tables are mapped through normalized headers such as project name, category, applicant, region, protection unit, representative inheritor, and level. Extraction derives deterministic fact IDs from the subject, predicate, object, and source ID. Generic extracted facts start as `verified=false` and stay out of QA and synthetic chunks until they are reviewed or deterministically verified.

National project extraction rejects rows whose project name does not match the page project. Applicant checks require the Qinghai province context and, for discovered catalog pages, agreement with the registered region. This keeps related-project tables from contributing facts that belong to other provinces or subprojects.

### 4.2 Deterministic inheritor verification

Representative-inheritor sources are discovered separately from project pages. The verifier requires exact agreement between catalog metadata and detail-page fields for person, project, category, applicant, and project number, and generates project–inheritor, category, applicant, national-level, and optional person–ethnic-group relations. Biography prose is never used for relation extraction.

### 4.3 Reviewed local catalogs

Scanned and office-document catalogs go through a human-review path. Each annotation records the official landing page, attachment URL, attachment SHA-256, review date and role, expected row count, and a complete structured transcription. OCR serves only as annotation assistance. A record becomes `manual_checked=true` only after row-by-row visual or structured-document confirmation.

The reviewed local material covers Huangzhong District project and inheritor lists and Guide County project inventories. Mixed historical taxonomies are normalized for graph use while the evidence keeps the source wording. Proposed public-notice lists are stored as proposals; the importer does not turn a proposed list into final level or location claims.

### 4.4 Museum object verification

Museum collection candidates come from the museum's official structured API. The collector validates the exhibit ID and museum ownership, hashes the stored API response, and keeps descriptions and media local under a conservative policy. Fact generation requires agreement among list metadata, detail fields, registry URL/status, and content hash, and produces category, period, holding-institution, and material relations. A fixed sample of ten objects and forty relations was checked manually, field by field.

### 4.5 Validation gates

The release validator checks:

- JSON/Pydantic schema validity;
- source, fact, chunk, and QA referential integrity;
- duplicate URLs and inconsistent source decisions;
- evidence requirements for facts and QA;
- release-policy compatibility with open text;
- restricted-domain and restricted-source text leakage;
- local/raw files accidentally tracked for release.

The current result is `errors=0, warnings=0`, and the restricted-source audit reports zero open-text violations. This is an engineering validation result — not a legal opinion, and not a guarantee that every factual claim is culturally authoritative.

### 4.6 Evidence minimization release blocker

The schema stores short evidence excerpts to support auditing. Some legacy national-project table excerpts may still carry adjacent public representative fields — sex or birth date, for example — that the released relation does not need. Current annotation policy already excludes such columns, so a field-level minimization audit and migration must run before the candidate can be labeled the final public release: keep the relation, the source URL, and the shortest sufficient evidence; drop the unrelated adjacent columns.

## 5. Benchmark Construction

### 5.1 QA generation

Only verified medium- and high-confidence facts are eligible. Single-fact questions require exactly one canonical answer for a subject–relation pair. Multi-hop questions combine supported relations for one entity and include every value when a relation is multi-valued. Comparisons stay within one entity type and exclude ties. Regional aggregation uses explicit `declared_by` or `located_in` semantics.

Metadata relations such as `related_to_concept` and `mentioned_in_source` stay available to the graph but are excluded from domain QA. Regional questions name the exact relation — “申报” or “流传地区” — instead of the vague “相关项目.” Aggregations with more than five answer projects are not generated, because they cannot be fairly supported within the default `top_k=5` budget.

### 5.2 Unanswerable questions and refusal

Unanswerable templates ask for plausible but absent attributes. Project questions cover protection-evaluation dates and scores, protection-plan identifiers, and dedicated funding. Museum questions cover excavation location, accession date, object grade, and restoration date. Person questions cover awards, formal disciples, public transmission activities, and complete work catalogs.

The evidence-only answerer applies a conservative requested-attribute support check: retrieving a related entity is not enough — the evidence must explicitly support the requested attribute. Under this policy the refusal rate on the current 100 unanswerable questions is 1.0000, and a stratified subset of these items went through the 300-record manual QA audit. Because the negatives are templated and the guard knows the attribute vocabulary, this score shows that the refusal mechanism works as designed, not that the system resists open-domain hallucination.

### 5.3 Manual QA review

QA review draws a deterministic stratified sample. Each displayed item shows the question, expected answer, exact evidence facts, source titles, and URLs. An accepted decision stores a SHA-256 of the QA snapshot, so a regenerated or edited question cannot inherit an old approval. The maintainer reviewed batches of twenty until 300 valid current snapshots were accepted; 67 decisions superseded by generator improvements were discarded.

Three correction examples are published in `audit_samples`:

| Failure | Action |
|---|---|
| Metadata relation entered a domain QA item | exclude metadata-only predicates from multi-hop/comparison generation |
| `located_in` question used ambiguous “related project” wording | explicitly ask for the recorded circulation area |
| One regional answer contained more than 100 projects | cap regional answer sets at five and regenerate |

### 5.4 Split policy and leakage

The RC exposes one `full` split per config and publishes no random train/validation/test division. Answerable QA is generated from the same verified fact universe that builds the chunks and the graph, so random row splits would scatter near-identical entities and relations across partitions. A later benchmark split will group by entity and evidence source, then verify that validation and test groups are disjoint from training evidence at the intended level.

## 6. Baseline Setup

### 6.1 Runtime

The audited AutoDL run used:

- Python 3.12.3;
- PyTorch 2.5.1 with CUDA 12.4;
- NVIDIA GeForce RTX 4090;
- `top_k=5` for evaluation;
- 948 indexed chunks;
- 512-dimensional normalized dense embeddings.

Model downloads go through a configurable Hugging Face mirror with a persistent cache; release upload uses the official Hugging Face endpoint. Derived stages store input fingerprints, and vector indexes are reused only when the chunk fingerprint and model configuration match.

### 6.2 Dense retrieval

The vector baseline uses [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5). Embeddings are L2-normalized and indexed with FAISS inner product. The audited index fingerprint is:

```text
6d304486f580ada3e27e7d42f9500cde9fce4e14bcc6163d53d59aba112ff67e
```

### 6.3 Sparse retrieval

BM25 uses jieba search-mode tokenization and Okapi BM25 over the same 948 release-safe chunks. It is built in memory and needs no separate persistent artifact.

### 6.4 Graph retrieval

The graph is a NetworkX multi-directed graph with entity nodes, source nodes, fact edges, and provenance edges; the current build has 1,521 nodes and 3,190 edges. Entity matching prefers the longest overlapping mention, so a query for a prefecture does not also expand from a contained province name. Relation cues add predicate-specific ranking bonuses, and multi-relation queries reserve a graph result for each explicitly requested predicate before filling the remaining budget.

### 6.5 Hybrid allocation and reranking

Dense and BM25 scores are max-normalized and combined with weights 0.6 and 0.4. The hybrid pool is merged with graph evidence, and the evidence allocator balances retrieval score, character overlap, confidence, and per-source diversity while keeping at least one traceable graph fact whenever graph matching succeeds.

Optional reranking uses [BAAI/bge-reranker-base](https://huggingface.co/BAAI/bge-reranker-base), which rescores candidates before evidence allocation. The reranker is off by default to keep CPU-only runs light; it was enabled explicitly for the audited comparison.

### 6.6 Evaluation metrics

- **Recall@5:** whether at least one gold evidence source appears in the top five;
- **MRR:** reciprocal rank of the first gold source;
- **Evidence hit rate:** whether a gold fact or gold source is present;
- **Mean source diversity:** number of distinct retrieved source IDs;
- **Unanswerable refusal rate:** fraction of unanswerable QA for which the evidence-only answerer refuses;
- **Citation presence:** fraction whose returned evidence has source IDs and URLs, with refusals treated as citation-safe.

The evaluation covers evidence retrieval and conservative refusal only. No LLM generation was involved, and semantic answer correctness was not scored.

## 7. Results

### 7.1 Main results

| Mode | Recall@5 | MRR | Evidence hit | Mean source diversity | Refusal | Citation |
|---|---:|---:|---:|---:|---:|---:|
| vector-only | 0.9767 | 0.9362 | 0.9767 | 4.589 | 1.0000 | 1.0000 |
| bm25-only | 0.9922 | 0.9745 | 0.9922 | 4.586 | 1.0000 | 1.0000 |
| graph-only | 0.9978 | **0.9889** | 0.9978 | 2.240 | 1.0000 | 1.0000 |
| hybrid | 0.9967 | 0.9881 | 0.9967 | **4.927** | 1.0000 | 1.0000 |
| vector-only+rerank | 0.9767 | 0.9579 | 0.9767 | 4.589 | 1.0000 | 1.0000 |
| bm25-only+rerank | 0.9922 | 0.9738 | 0.9922 | 4.586 | 1.0000 | 1.0000 |
| graph-only+rerank | 0.9978 | 0.9709 | 0.9978 | 2.240 | 1.0000 | 1.0000 |
| hybrid+rerank | **1.0000** | 0.9787 | **1.0000** | 4.716 | 1.0000 | 1.0000 |

All modes evaluated 1,000 questions. Recall, MRR, and evidence hit are computed on 900 answerable records; refusal is computed on 100 unanswerable records.

### 7.2 Interpretation

BM25 clearly outperforms vector-only retrieval on this snapshot, and the reason is simple: questions and chunks share exact entity and relation vocabulary, and lexical matching exploits that directly. On data like this, BM25 is a serious baseline.

Graph-only retrieval delivers the best ranking quality. Explicit entity and relation matching aligns closely with facts that themselves generated the QA. Its low source diversity is expected — graph retrieval concentrates on a small set of directly connected facts.

Hybrid retrieval has the highest non-reranked diversity and nearly the best MRR. Hybrid plus reranking is the only mode with perfect Recall@5, yet its MRR falls below the non-reranked graph and hybrid modes: the reranker improves candidate coverage and ordering in some dense cases but does not uniformly help queries the graph already structures well.

No latency or cost measurements were recorded in this RC, so these results cannot support claims of operational superiority; that would require timing, memory, and cold-start data.

## 8. Failure Analysis

### 8.1 Data extraction failures

National pages can include “related project” or representative tables spanning multiple subprojects, and early extraction sometimes admitted facts from the wrong row or region. The final extractor requires project-title and registered-applicant agreement, reruns from scratch after rule changes, and removes stale auto-generated facts.

Some official provincial URLs under `/content/{id}` consistently returned server error 500 while other path families succeeded. The 33 failures stay in the registry; they are neither retried indefinitely nor counted as parsed coverage.

### 8.2 Chunking failure

An early cursor-update bug produced dozens of overlapping tail chunks for short documents: four trial pages generated 246 open-text chunks, including repeated ranges ending at the same character. After the chunker was fixed to guarantee forward progress, the same trial pages produced 13 chunks, and the final 122-source open-text corpus produces 353.

### 8.3 Retrieval failures

After the open-text expansion, vector evidence from broad cultural-tourism articles began crowding out exact regional facts, and graph matching initially preferred related inheritor edges or province-wide entities. Longest-mention matching, relation-cue scoring, and predicate reservation fixed the observed regional and multi-hop misses; graph-only Recall@5 rose to 0.9978, and hybrid with reranking reaches 1.0000 on the current QA.

One multi-hop question about Rebgong art required both the applicant and a specific representative inheritor, but several equally scored inheritor edges filled the budget and displaced the applicant fact. Predicate reservation now guarantees each requested relation at least one graph result.

### 8.4 Benchmark-design failures

Manual QA review surfaced problems that aggregate metrics would never show:

- metadata provenance was phrased as cultural knowledge;
- `located_in` templates used ambiguous “related to region” wording;
- one regional answer exceeded 100 items and was impossible under `top_k=5`;
- duplicate aliases could create repetitive subjects;
- generated questions were initially concentrated on a small number of entities.

The fixes all operate at generator level, followed by full regeneration and hash-aware re-review; superseded approvals do not carry over to changed records.

### 8.5 Refusal failure

Before the requested-attribute guard was aligned with the new unanswerable templates, non-reranked modes returned related evidence for every unanswerable question — a refusal rate of 0.0 — while reranked modes refused only incidentally, when scores fell below a global threshold. The retrieval index was not at fault; the answerer simply recognized only older intents such as ticket price and visitor count.

The corrected answerer requires support for the benchmark's requested attributes, including accession date, object grade, protection assessment, protection-plan identifier, public transmission activity, and related fields. A positive unit test confirms that evidence containing the requested attribute is not refused. The resulting 1.0000 refusal score is transparent but template-dependent.

## 9. Ethical and Release Considerations

### 9.1 Cultural authority and representation

Official records support auditability, but they reflect institutional publication practices. They may miss community terminology, contested ownership, living transmission, oral variation, and local perspectives. In this dataset, “verified” means agreement with registered evidence and pipeline checks — not universal cultural truth.

Project-authored summaries must stay labeled as synthetic. Users should follow the source link, preserve historical wording where it matters, and avoid using the dataset to declare authenticity, ownership, ethnic identity, or heritage status beyond what the cited record states.

### 9.2 Personal information

Public representative names and project relations appear where the benchmark needs them. Detailed addresses, contact details, identification numbers, and unnecessary biography fields fall outside the intended schema. The evidence-minimization blocker in Section 4.6 must be resolved before final public labeling. Audit exports strip reviewer identity and local paths.

### 9.3 Copyright and attribution

The code license does not create a blanket dataset-content license. Each source row carries its own release decision. Restricted and unclear sources contribute metadata and conservative facts, not copied prose. Permitted government-public chunks retain their source attribution and URL. Museum images, 3D assets, and curatorial prose are not released by default.

### 9.4 Takedown and correction

A rights holder or source institution can request removal or correction. The maintenance procedure is to disable the affected collection, remove or downgrade public records, rebuild dependent entities, chunks, QA, and indexes, increment the version, regenerate checksums, and document the change. Source history is retained only when appropriate.

### 9.5 Public release surfaces

The intended release architecture is:

- **Hugging Face Dataset:** canonical public data entry, configs, Viewer, checksums, reports, and DOI-capable versioning;
- **GitHub:** collection pipeline, schemas, validation, baselines, tests, and reproducibility instructions;
- **Technical Report:** design rationale, experimental setup, failures, ethics, and limitations;
- **Hugging Face Space:** evidence-only interactive retrieval demo with citations and explicit refusal.

The Space should load the published data version rather than private AutoDL files, display source links, avoid an unreviewed generative backend by default, and show the dataset version behind every response.

## 10. Limitations and Future Versions

### 10.1 Current limitations

1. **Scale:** entities, facts, and chunks remain below final V1 targets.
2. **Coverage:** ecological tourism, cultural-tourism policy, and Haibei sources remain below configured minima.
3. **Institutional bias:** official sources dominate; community and oral perspectives are underrepresented.
4. **Text-only representation:** images, audio, performance, geography, and embodied practice are absent.
5. **Evidence minimization:** some legacy structured excerpts still need field-level redaction.
6. **No leakage-safe partition:** the RC publishes only a `full` QA split.
7. **No generative-answer evaluation:** baseline metrics cover retrieval and conservative refusal only.
8. **No efficiency benchmark:** latency, memory, index-build time, and operating cost are not reported.
9. **Temporal versioning:** source claims can change, but the fact schema has limited validity-period support.
10. **Template effects:** QA wording and the refusal guard share a controlled attribute vocabulary.

### 10.2 Planned work

Before final V1:

- complete the evidence excerpt minimization audit;
- add at least two parsed Haibei sources, eight ecological-tourism sources, and forty policy sources;
- expand structured official facts and release-safe chunks without weakening policy gates;
- reach at least 2,000 entities, 10,000 facts, and 10,000 chunks;
- construct entity/source-aware QA partitions and audit leakage;
- add retrieval latency and memory measurements;
- publish the six-config HF dataset with a version tag and DOI;
- render this report as a versioned PDF;
- deploy an evidence-only Hugging Face Space pinned to the released dataset revision.

Later versions should also add source update dates and validity periods, correction lineage, community review where feasible, and richer spatial/multimodal metadata without redistributing protected media.

## Reproducibility Appendix

### A.1 Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### A.2 Validate and build derived artifacts

```bash
python scripts/09_validate_release.py
python scripts/11_dataset_stats.py
python scripts/17_audit_source_coverage.py

python scripts/07_build_graph.py --no-resume
python scripts/06_build_vector_index.py \
  --device cuda \
  --batch-size 128 \
  --no-resume
```

### A.3 Evaluate

```bash
python -m qinghai_rag.rag.evaluate \
  --device cuda \
  --rerank \
  --top-k 5
```

Expected reports:

```text
data/release/validation_report.md
data/interim/dataset_stats.json
data/interim/dataset_stats.md
data/interim/source_coverage_report.json
data/interim/source_coverage_report.md
data/interim/eval_report.json
data/interim/eval_report.md
```

### A.4 Export Hugging Face configs

```bash
python scripts/10_export_hf_dataset.py \
  --output data/release/hf_publish_v1_rc1
```

After review and authentication:

```bash
HF_ENDPOINT=https://huggingface.co \
python scripts/10_export_hf_dataset.py \
  --output data/release/hf_publish_v1_rc1 \
  --push \
  --repo-id zhangjh123/QinghaiRAG
```

The release exporter refuses to package a formal snapshot when validation, statistics, coverage, or evaluation reports are missing. The development-only `--allow-missing-reports` option must not be used for a public release.

## References and Project Artifacts

- QinghaiRAG code repository: <https://github.com/jiaheng-math/QinghaiRAG>
- QinghaiRAG dataset repository: <https://huggingface.co/datasets/zhangjh123/QinghaiRAG>
- China Intangible Cultural Heritage website: <https://www.ihchina.cn/>
- Qinghai Department of Culture and Tourism: <http://whlyt.qinghai.gov.cn/>
- Guide County Government tourism portal: <https://www.guide.gov.cn/gdly>
- Huangzhong District Government: <https://www.huangzhong.gov.cn/>
- Qinghai Tibetan Culture Museum: <https://www.tibetanculturemuseum.com.cn/pcweb/>
- BGE small Chinese embedding model: <https://huggingface.co/BAAI/bge-small-zh-v1.5>
- BGE reranker base: <https://huggingface.co/BAAI/bge-reranker-base>
- Hugging Face DOI documentation: <https://huggingface.co/docs/hub/doi>
- FAISS: <https://github.com/facebookresearch/faiss>
- NetworkX: <https://networkx.org/>
