# Datasheet for QinghaiRAG

## Motivation

The dataset supports auditable Chinese RAG research in a geographically and culturally specific domain where evidence is fragmented and reuse terms vary. It prioritizes provenance, refusal, and source policy over corpus size.

## Composition

Five linked JSONL tables contain sources, entities, facts, open/synthetic chunks, and QA. Stable IDs form the joins. Public releases exclude raw HTML and local-only documents.

The three explicit scale tiers are:

- Toy seed: 5–20 sources, 20–100 entities, 50–200 facts, 20–100 chunks, and 20–50 QA. This is only a smoke test.
- v0.1 showcase: 100–300 sources, 500–1,500 entities, 2,000–8,000 facts, 2,000–8,000 chunks, and 300–800 QA; 100–200 QA and 300–500 facts should be manually checked.
- v1.0 benchmark: 500–1,500 sources, 2,000–8,000 entities, 10,000–50,000 facts/chunks, and 1,000–3,000 QA, including 300–800 manually verified QA.

The intended curation mix is approximately 40% structured facts/triples, 30% project-authored synthetic fact chunks, 20% redistributable official text chunks, and 10% QA evaluation work. Provenance and licence quality take priority over hitting a numerical range.

## Collection process

Maintainers register page-level seeds, assess preliminary terms, respect robots rules, use a named user agent and request interval, hash retrieved HTML, and store raw material locally. Page content is checked for restriction phrases after retrieval. Failures remain visible in the registry.

## Source policy

Official national/provincial pages are preferred. Restricted sources are metadata/facts only. Commercial guides, social platforms, encyclopedias, and unclear scans are excluded by default. Public accessibility alone never authorizes full-text redistribution.

## Annotation process

Rules/table parsers propose facts as `verified=false`. Reviewers confirm subject/object types, relation direction, evidence, source, aliases, and confidence. Verified facts generate conservative synthetic chunks and templated QA. Questions are manually checked for answerability and leakage.

## Quality control

Pydantic validates records. Release validation checks referential integrity, policies, restricted domains, duplicate URLs/text, evidence requirements, JSON syntax, and tracked raw data. `11_dataset_stats.py` reports tier readiness, all required distributions, per-source contributions, and restricted-source chunk leakage. Retrieval metrics and manual failure analysis accompany a research release.

## Intended uses

Dataset pipelines, RAG/Graph RAG baselines, evidence allocation, citation and refusal research, and non-authoritative cultural knowledge discovery.

## Out-of-scope uses

Claims about cultural ownership/authenticity, high-stakes decisions, unrestricted content scraping, reproducing protected text, profiling people/communities, or presenting generated summaries as official descriptions.

## Limitations

The corpus reflects source institutions and may underrepresent community voices. Administrative aliases and names change. Retrieval evidence does not prove truth. Some factual relations can be publishable while the underlying wording is not. Temporal facts need dates/versioning in later schemas.

## Maintenance

Maintainers review takedowns, source changes, conflicts, and corrections; rebuild dependent outputs after modifications; publish versioned validation/evaluation reports; and document contributor/reviewer roles. Contact information must replace placeholders before real crawling.
