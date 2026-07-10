# Annotation guide

## Entity types

`ICH_PROJECT`, `REGION`, `CATEGORY`, `PERSON`, `ORGANIZATION`, `ETHNIC_GROUP`, `SCENIC_SPOT`, `FESTIVAL_EVENT`, and `CONCEPT`.

Use the narrowest supported type. An administrative region used as an applicant can remain `REGION`; do not relabel it as an organization merely to fit a relation. Record a canonical form plus literal aliases found in evidence.

## Relations

- `belongs_to_category`: project → category
- `located_in`: project → region
- `declared_by`: project → organization or region
- `protected_by`: project → organization
- `inherited_by`: project → person (this project uses this direction consistently)
- `associated_with_ethnic_group`: project → ethnic group
- `related_to_festival`: project → festival/event
- `mentioned_in_source`: project → source title/concept
- `has_level`: project → level concept
- `related_to_concept`: entity → concept

Never create a relation without `evidence_source_id`. Evidence should be the shortest sufficient sentence/table row and no more than necessary for audit.

## Labels

Topic labels use stable concepts such as `非遗`, `传统美术`, `传统技艺`, `民族文化`, `博物馆`, and `生态旅游`. Region labels use normalized forms: `青海省`, `西宁市`, `海东市`, `海北州`, `黄南州`, `海南州`, `果洛州`, `玉树州`, and `海西州`.

## Confidence

- `high`: explicit value in a reliable structured source, reviewed against its evidence.
- `medium`: explicit but ambiguous/partially structured, or one normalizing judgment remains.
- `low`: inferred, fuzzy matched, conflicting, or evidence incomplete. Keep in interim by default.

Fuzzy matching is a review suggestion, never automatic authority. Similar person/project names must not be merged solely on edit similarity.

`manual_checked=true` means a human reviewer opened the exact source and completed the checklist below. `manual_seed`, `verified=true`, or a toy record does not by itself count as manual review. This distinction is used by the v0.1/v1.0 scale report.

Reviewed scanned catalogs must also record the official landing page and attachment URLs, the attachment SHA-256, review date and role, expected row count, and the complete reviewed transcription. OCR is annotation assistance only: its output is never marked verified without row-by-row visual confirmation. Reviewed transcriptions live under `annotations/local_catalogs/`; raw PDFs remain ignored.

Public-notice candidate lists must set `publication_status: proposed` and record an explicit `proposed_concept`. Their importer may retain the reviewed category and candidate-list relation, but it must not emit `has_level` or `located_in` as though the list had already been finally approved.

Representative-inheritor imports retain only the minimum benchmark fields needed for a public relation (normally project name and public representative name). Sex, birth date, detailed address, telephone number, identification number, and other unnecessary personal columns are excluded from reviewed annotations and release facts even when they appear in an official attachment.

When the same approved official record explicitly states a project's level, the corresponding inheritor row may include `project_level`. Omit it from every row where the level applies only to the representative person or is otherwise ambiguous.

Mixed-level resource inventories may set `level`, `source_sequence`, `inheritors`, and (when source punctuation or typography is not a stable entity name) `canonical_project_name` per project row. The evidence retains the source project name while the graph uses the reviewed canonical name. Legacy source categories such as `民间音乐`, `民间舞蹈`, and `岁时节令` are normalized to the benchmark taxonomy without changing the quoted evidence.

Museum-object manual review samples live under `annotations/museum_reviews/`. Each fixed row records the official exhibit ID and all four expected relation values. The review applier requires a parsed source, a recorded content hash, an exact four-fact set, and high-confidence deterministic verification before it can set `manual_checked=true`; the source content hash and review ID are added to every reviewed fact.

## Conflicts

Retain both evidence-backed facts, mark them unverified or lower confidence, and explain the conflict in `notes`. Do not create a deterministic synthetic sentence or QA answer until a reviewer resolves the scope/date/identity issue. Do not silently select the newest page without checking what changed.

## Manual verification checklist

- Open the exact source URL and confirm title/publisher.
- Confirm reuse policy and absence/presence of page-level restrictions.
- Match subject, predicate direction, object, and evidence text.
- Confirm administrative and entity normalization; preserve aliases.
- Check whether the claim is time-dependent.
- Check for conflicting records and homonyms.
- Mark reviewer decision through `verified`, `confidence`, and `notes`.
- Re-run release validation and inspect downstream QA/chunks.
