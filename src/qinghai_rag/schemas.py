from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Confidence = Literal["high", "medium", "low"]


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceType(StrEnum):
    NATIONAL_OFFICIAL_DATABASE = "national_official_database"
    PROVINCIAL_GOVERNMENT = "provincial_government"
    PROVINCIAL_CULTURE_TOURISM_DEPARTMENT = "provincial_culture_tourism_department"
    MUNICIPAL_OR_COUNTY_GOVERNMENT = "municipal_or_county_government"
    MUSEUM_OR_SCENIC_SPOT_OFFICIAL = "museum_or_scenic_spot_official"
    RESTRICTED_REFERENCE = "restricted_reference"
    OTHER = "other"


class LicenseStatus(StrEnum):
    OPEN = "open"
    GOVERNMENT_PUBLIC = "government_public"
    UNCLEAR = "unclear"
    RESTRICTED = "restricted"
    FORBIDDEN = "forbidden"


class ReleasePolicy(StrEnum):
    FULL_TEXT_ALLOWED = "full_text_allowed"
    GOVERNMENT_PUBLIC = "government_public"
    SHORT_EXCERPT_ONLY = "short_excerpt_only"
    METADATA_AND_FACTS_ONLY = "metadata_and_facts_only"
    LOCAL_ONLY = "local_only"
    EXCLUDE = "exclude"


class CrawlStatus(StrEnum):
    PENDING = "pending"
    FETCHED = "fetched"
    PARSED = "parsed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SourceCandidateRecord(StrictRecord):
    candidate_id: str
    source_id: str
    title: str
    publisher: str
    source_type: SourceType = SourceType.OTHER
    url: str
    domain: str
    province: str = "青海省"
    region: list[str] = Field(default_factory=list)
    topic: list[str] = Field(default_factory=list)
    license_status: LicenseStatus = LicenseStatus.UNCLEAR
    release_policy: ReleasePolicy = ReleasePolicy.METADATA_AND_FACTS_ONLY
    raw_text_release: bool = False
    discovery_method: Literal[
        "ihchina_catalog", "ihchina_inheritor_catalog", "whlyt_search", "manual"
    ]
    discovered_at: str
    review_status: ReviewStatus = ReviewStatus.PENDING
    catalog_metadata: dict[str, str] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("discovered_at")
    @classmethod
    def valid_discovery_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


class SourceRecord(StrictRecord):
    source_id: str
    title: str
    publisher: str = ""
    source_type: SourceType = SourceType.OTHER
    url: str
    domain: str
    language: str = "zh"
    province: str = "青海省"
    region: list[str] = Field(default_factory=list)
    topic: list[str] = Field(default_factory=list)
    retrieved_at: str
    license_status: LicenseStatus = LicenseStatus.UNCLEAR
    release_policy: ReleasePolicy = ReleasePolicy.METADATA_AND_FACTS_ONLY
    raw_text_release: bool = False
    crawl_status: CrawlStatus = CrawlStatus.PENDING
    content_sha256: str = ""
    notes: str = ""

    @field_validator("retrieved_at")
    @classmethod
    def valid_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def enforce_release_policy(self) -> "SourceRecord":
        denied = {
            ReleasePolicy.METADATA_AND_FACTS_ONLY,
            ReleasePolicy.LOCAL_ONLY,
            ReleasePolicy.EXCLUDE,
            ReleasePolicy.SHORT_EXCERPT_ONLY,
        }
        if self.release_policy in denied and self.raw_text_release:
            raise ValueError("raw_text_release must be false for non-full-text policies")
        return self


class EntityRecord(StrictRecord):
    entity_id: str
    name: str
    type: Literal[
        "ICH_PROJECT",
        "REGION",
        "CATEGORY",
        "PERSON",
        "ORGANIZATION",
        "ETHNIC_GROUP",
        "SCENIC_SPOT",
        "FESTIVAL_EVENT",
        "CONCEPT",
    ]
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    province: str = "青海省"
    regions: list[str] = Field(default_factory=list)
    canonical_source_id: str
    confidence: Confidence = "medium"
    notes: str = ""


class FactRecord(StrictRecord):
    fact_id: str
    subject: str
    subject_type: str
    predicate: Literal[
        "belongs_to_category",
        "located_in",
        "declared_by",
        "protected_by",
        "inherited_by",
        "associated_with_ethnic_group",
        "related_to_festival",
        "mentioned_in_source",
        "has_level",
        "related_to_concept",
    ]
    object: str
    object_type: str
    evidence_source_id: str
    evidence_url: str
    evidence_text: str | None = None
    extraction_method: Literal[
        "rule", "table_parse", "llm_assisted", "manual_seed", "manual_review"
    ]
    verified: bool = False
    confidence: Confidence = "medium"
    manual_checked: bool = False
    notes: str = ""

    @field_validator("evidence_source_id")
    @classmethod
    def source_required(cls, value: str) -> str:
        if not value:
            raise ValueError("facts require evidence_source_id")
        return value


class ChunkRecord(StrictRecord):
    chunk_id: str
    doc_id: str
    source_id: str
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    topic_labels: list[str] = Field(default_factory=list)
    region_labels: list[str] = Field(default_factory=list)
    entity_mentions: list[str] = Field(default_factory=list)
    license_status: LicenseStatus
    release_policy: ReleasePolicy
    source_url: str
    retrieved_at: str
    chunk_kind: Literal["open_text", "synthetic_fact"] = "open_text"
    notes: str = ""

    @model_validator(mode="after")
    def valid_offsets_and_policy(self) -> "ChunkRecord":
        if self.char_end < self.char_start:
            raise ValueError("char_end must be >= char_start")
        if self.release_policy not in {
            ReleasePolicy.FULL_TEXT_ALLOWED,
            ReleasePolicy.GOVERNMENT_PUBLIC,
        }:
            raise ValueError("public chunks require a full-text-compatible release policy")
        return self


class QARecord(StrictRecord):
    question_id: str
    question: str
    answer: str
    answer_type: Literal[
        "single_fact", "multi_hop", "regional_aggregation", "comparison", "unanswerable"
    ]
    evidence_fact_ids: list[str] = Field(default_factory=list)
    evidence_source_ids: list[str] = Field(default_factory=list)
    required_entities: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    unanswerable: bool = False
    manual_checked: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def evidence_or_unanswerable(self) -> "QARecord":
        if self.unanswerable:
            if self.answer_type != "unanswerable":
                raise ValueError("unanswerable records must use answer_type=unanswerable")
        elif not self.evidence_source_ids or not self.evidence_fact_ids:
            raise ValueError("answerable QA requires evidence fact and source IDs")
        return self


RELEASE_MODELS = {
    "qinghai_sources.jsonl": SourceRecord,
    "qinghai_entities.jsonl": EntityRecord,
    "qinghai_facts.jsonl": FactRecord,
    "qinghai_chunks_open.jsonl": ChunkRecord,
    "qinghai_qa_eval.jsonl": QARecord,
}
