"""Data models for semantic SQL planning."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SQLPlan(BaseModel):
    """Structured SQL plan derived from a validated requirement analysis."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    report_type: str = Field(description="Supported report type.")
    source_table: str = Field(description="Primary source table or view.")
    filters: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[str] = Field(default_factory=list)
    calculations: list[str] = Field(default_factory=list)
    ranking: list[str] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)
    order_by: list[str] = Field(default_factory=list)
    applied_business_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

