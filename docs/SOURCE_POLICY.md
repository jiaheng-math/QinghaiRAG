# Source policy

## Principle

QinghaiRAG does not treat “publicly accessible” as equivalent to “full text may be redistributed.” A URL, factual observation, original expression, image, and audiovisual work can have different legal and ethical constraints.

## Release classes

- `full_text_allowed`: explicit open terms or documented permission permits redistribution.
- `government_public`: a reviewed government public document/report without a page-level restriction. Provenance is still mandatory.
- `short_excerpt_only`: only a necessary short excerpt may be kept after review; it is not an automatic path into open chunks.
- `metadata_and_facts_only`: release source metadata and conservative, verified facts; do not release copied prose.
- `local_only`: material may support private analysis but never the public dataset.
- `exclude`: do not collect into the dataset package.

Unknown terms default to `metadata_and_facts_only`, `license_status=unclear`, and `raw_text_release=false`.

## Overrides

Restricted/excluded domains and strong phrases (`未经许可不得转载`, `严禁转载`, `禁止复制`, `版权所有`) override seed metadata. A maintainer must never weaken an override merely because a page is convenient to access. Government status is not a blanket licence for every embedded asset or third-party quotation.

## Storage

Raw HTML exists only in `data/raw/`, is ignored by Git, and is never exported to Hugging Face. Interim cleaned documents and evidence excerpts remain local. Images, audio, and video are not collected or redistributed by default.

For restricted sources, project-authored synthetic chunks may summarize verified facts conservatively. They must say they are generated summaries, retain `source_id` and URL, avoid copied expression, and must not conceal conflicting facts.

## Takedowns and corrections

If a rights holder asks for removal, maintainers should disable collection, remove affected public chunks/facts when appropriate, regenerate downstream entities/QA/indexes, increment the dataset version, and document the change. A source URL remains only when legally appropriate for audit history.

This policy is an engineering safeguard, not legal advice. Material release should receive jurisdiction-appropriate review.
