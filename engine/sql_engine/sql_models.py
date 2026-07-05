"""SQL engine data models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SQLGenerationStatus(str, Enum):
    """Lifecycle status for SQL generation output."""

    BLOCKED = "SQL_BLOCKED"
    GENERATED = "SQL_GENERATED"


class SQLGenerationResult(BaseModel):
    """Structured result returned by the SQL generator."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    status: SQLGenerationStatus = Field(description="SQL generation status.")
    sql: str | None = Field(default=None, description="Generated SQL text.")
    report_type: str | None = Field(default=None, description="Report type generated.")
    reason: str | None = Field(
        default=None,
        description="Reason SQL generation was blocked or completed.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings about the generated SQL.",
    )
    source_tables: list[str] = Field(
        default_factory=list,
        description="Source tables or views referenced by the SQL.",
    )
    applied_business_rules: list[str] = Field(
        default_factory=list,
        description="Business rules applied while generating SQL.",
    )
