"""Data models for the AI Business Analyst requirement engine.

This module defines the structured objects used to represent a business
requirement analysis before SQL generation. The classes are intentionally
limited to schema definitions, validation constraints, enums, and
serialization-friendly Pydantic configuration.

No orchestration, prompt construction, SQL generation, or business-rule
execution logic belongs in this module.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RequirementStatus(str, Enum):
    """Lifecycle status of a requirement analysis."""

    DRAFT = "draft"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_SQL = "ready_for_sql"
    BLOCKED = "blocked"


class DecisionStatus(str, Enum):
    """Final decision status for downstream SQL generation."""

    SQL_ALLOWED = "SQL_ALLOWED"
    SQL_BLOCKED = "SQL_BLOCKED"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"


class QuestionPriority(str, Enum):
    """Priority level for a clarification question."""

    BLOCKER = "blocker"
    IMPORTANT = "important"
    OPTIONAL = "optional"


class BusinessRuleStatus(str, Enum):
    """Documentation status for a referenced business rule."""

    DOCUMENTED = "documented"
    PARTIALLY_DOCUMENTED = "partially_documented"
    UNKNOWN = "unknown"


class DatabaseObjectType(str, Enum):
    """Supported database object categories for candidate sources."""

    TABLE = "table"
    VIEW = "view"
    METADATA_VIEW = "metadata_view"
    UNKNOWN = "unknown"


class RequirementFieldStatus(str, Enum):
    """Completeness status for an individual requirement field."""

    PROVIDED = "provided"
    ASSUMED = "assumed"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class KnownInformation(BaseModel):
    """Information already known from the stakeholder request or project context.

    This model captures the business facts that can be safely used during
    requirement analysis. Values should come from the request, documented
    knowledge, or explicit user confirmation.

    JSON serialization is available through Pydantic's ``model_dump`` and
    ``model_dump_json`` methods.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    business_objective: str | None = Field(
        default=None,
        min_length=1,
        description="Business purpose or decision the report should support.",
    )
    stakeholder: str | None = Field(
        default=None,
        min_length=1,
        description="Person, team, or audience requesting the analysis.",
    )
    report_type: str | None = Field(
        default=None,
        min_length=1,
        description="High-level report type, such as auction, TeaMart, tasting, buyer, seller, or garden analysis.",
    )
    season: int | None = Field(
        default=None,
        ge=1900,
        le=2200,
        description="Business season referenced by the request.",
    )
    seasons: list[int] = Field(
        default_factory=list,
        description="Multiple business seasons referenced by comparison requests.",
    )
    sale_range: str | None = Field(
        default=None,
        min_length=1,
        description="Requested sale range, preserved as stakeholder-provided text.",
    )
    garden: str | None = Field(
        default=None,
        min_length=1,
        description="Requested garden or mark name, if the report is garden-specific.",
    )
    buyer: str | None = Field(
        default=None,
        min_length=1,
        description="Requested buyer or buyer group, if the report is buyer-specific.",
    )
    area: str | None = Field(
        default=None,
        min_length=1,
        description="Requested business area or area alias.",
    )
    centre: str | None = Field(
        default=None,
        min_length=1,
        description="Requested auction centre or centre group.",
    )
    category: str | None = Field(
        default=None,
        min_length=1,
        description="Requested tea category, such as CTC or ORTHODOX.",
    )
    tea_type: str | None = Field(
        default=None,
        min_length=1,
        description="Requested tea type, if relevant.",
    )
    sub_tea_type: str | None = Field(
        default=None,
        min_length=1,
        description="Requested sub-tea type, if relevant.",
    )
    est_blf: str | None = Field(
        default=None,
        min_length=1,
        description="Requested EST/BLF filter or grouping.",
    )
    lot_status: str | None = Field(
        default=None,
        min_length=1,
        description="Requested lot status handling, if it affects quantity or value logic.",
    )
    metrics: list[str] = Field(
        default_factory=list,
        description="Metrics requested by the stakeholder.",
    )
    output_grain: str | None = Field(
        default=None,
        min_length=1,
        description="Expected row-level grain, such as garden-wise, buyer-wise, grade-wise, or sale-wise.",
    )
    output_format: str | None = Field(
        default=None,
        min_length=1,
        description="Requested output format or layout.",
    )
    raw_request_text: str | None = Field(
        default=None,
        min_length=1,
        description="Original stakeholder request text.",
    )


class MissingInformation(BaseModel):
    """A missing or ambiguous requirement element.

    Each instance represents one requirement field that must be clarified,
    assumed, or marked as unknown before SQL generation can be considered.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    field_name: str = Field(
        min_length=1,
        description="Name of the missing or ambiguous requirement field.",
    )
    status: RequirementFieldStatus = Field(
        description="Completeness status of the field.",
    )
    reason: str = Field(
        min_length=1,
        description="Why the field is missing, ambiguous, unknown, or assumed.",
    )
    blocks_sql_generation: bool = Field(
        default=True,
        description="Whether this missing information prevents SQL generation.",
    )


class ClarificationQuestion(BaseModel):
    """Question that should be asked to complete or validate the requirement.

    Questions should be specific, business-facing, and limited to information
    needed for the current request.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    question_id: str | None = Field(
        default=None,
        min_length=1,
        description="Optional stable catalogue identifier, such as Q001_Season.",
    )
    question: str = Field(
        min_length=1,
        description="Clarification question to ask the stakeholder.",
    )
    priority: QuestionPriority = Field(
        description="Whether the question is a blocker, important, or optional.",
    )
    related_field: str = Field(
        min_length=1,
        description="Requirement field the question is intended to clarify.",
    )
    expected_answer_format: str | None = Field(
        default=None,
        min_length=1,
        description="Expected answer shape, such as a year, sale range, category list, or yes/no.",
    )


class BusinessRuleReference(BaseModel):
    """Reference to a business rule relevant to the requirement.

    The reference should point to documented business knowledge when available.
    If the rule is not documented, use ``BusinessRuleStatus.UNKNOWN``.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    rule_id: str | None = Field(
        default=None,
        min_length=1,
        description="Business rule identifier, such as BR-002.",
    )
    name: str = Field(
        min_length=1,
        description="Human-readable business rule name.",
    )
    file_path: str | None = Field(
        default=None,
        min_length=1,
        description="Relative path to the rule document in knowledge/business.",
    )
    status: BusinessRuleStatus = Field(
        description="Documentation status of the business rule.",
    )
    relevance: str = Field(
        min_length=1,
        description="Why this rule matters for the current requirement.",
    )


class CandidateDatabaseObject(BaseModel):
    """Candidate table, view, or metadata source for the requirement.

    This model describes possible database sources identified during analysis.
    It does not assert that SQL generation is allowed.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    object_name: str = Field(
        min_length=1,
        description="Fully qualified table or view name when known.",
    )
    object_type: DatabaseObjectType = Field(
        description="Database object category.",
    )
    purpose: str = Field(
        min_length=1,
        description="Why this object may be relevant to the requirement.",
    )
    important_columns: list[str] = Field(
        default_factory=list,
        description="Columns likely needed from this object.",
    )
    join_keys: list[str] = Field(
        default_factory=list,
        description="Known join keys or join expressions involving this object.",
    )
    filters: list[str] = Field(
        default_factory=list,
        description="Common or requirement-specific filters for this object.",
    )
    confidence: RequirementFieldStatus = Field(
        default=RequirementFieldStatus.UNKNOWN,
        description="Confidence level for using this object in the requirement.",
    )


class ResolvedBusinessRule(BaseModel):
    """Business rule selected as applicable to a requirement."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    rule_id: str = Field(description="Rule identifier, such as BR-006.")
    name: str = Field(description="Human-readable business rule name.")
    file_path: str = Field(description="Source markdown file path.")
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    report_types: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    applies_because: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)


class BusinessRuleResolution(BaseModel):
    """Result of resolving business rules for a requirement."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    applicable_rules: list[ResolvedBusinessRule] = Field(default_factory=list)
    missing_rule_dependencies: list[str] = Field(default_factory=list)


class DatabaseResolution(BaseModel):
    """Result of mapping a requirement to likely database objects."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    candidate_database_objects: list[CandidateDatabaseObject] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)


class RequirementAnalysis(BaseModel):
    """Complete structured result of business requirement analysis.

    This top-level model is the handoff object between requirement analysis and
    later steps such as prompt construction, validation, SQL generation, or SQL
    review. SQL generation should only be considered when ``status`` and
    ``sql_generation_allowed`` indicate readiness and no blocker questions
    remain.

    JSON serialization is supported by Pydantic through ``model_dump`` and
    ``model_dump_json``.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    requirement_id: str | None = Field(
        default=None,
        min_length=1,
        description="Optional request or requirement identifier.",
    )
    status: RequirementStatus = Field(
        default=RequirementStatus.DRAFT,
        description="Current analysis status.",
    )
    summary: str = Field(
        min_length=1,
        description="Business-facing summary of the requirement.",
    )
    known_information: KnownInformation = Field(
        description="Known business information extracted from the request and project context.",
    )
    missing_information: list[MissingInformation] = Field(
        default_factory=list,
        description="Missing, ambiguous, unknown, or assumed fields.",
    )
    clarification_questions: list[ClarificationQuestion] = Field(
        default_factory=list,
        description="Questions required to complete or validate the requirement.",
    )
    business_rules: list[BusinessRuleReference] = Field(
        default_factory=list,
        description="Business rules relevant to the requirement.",
    )
    candidate_database_objects: list[CandidateDatabaseObject] = Field(
        default_factory=list,
        description="Candidate tables, views, or metadata objects for later SQL work.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions made during requirement analysis.",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Known business, data, or interpretation risks.",
    )
    sql_generation_allowed: bool = Field(
        default=False,
        description="Whether the requirement is sufficiently complete for SQL generation.",
    )
    decision_status: DecisionStatus | None = Field(
        default=None,
        description="Final SQL-readiness decision after validation and resolution.",
    )
    decision_reason: str | None = Field(
        default=None,
        min_length=1,
        description="Business-facing reason for the decision.",
    )
    next_action: str | None = Field(
        default=None,
        min_length=1,
        description="Recommended next action for the analyst or downstream engine.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional non-business metadata for calling systems.",
    )
