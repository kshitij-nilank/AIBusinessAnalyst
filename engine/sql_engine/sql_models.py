"""SQL engine data models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SQLGenerationStatus(str, Enum):
    """Lifecycle status for SQL generation output."""

    DRAFT = "draft"
    BLOCKED = "blocked"
    GENERATED = "generated"


class SQLTemplateReference(BaseModel):
    """Reference to a SQL template file."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    template_name: str = Field(description="Template identifier.")
    template_path: Path = Field(description="Path to the SQL template file.")


class SQLGenerationResult(BaseModel):
    """Structured result returned by the SQL generator."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    status: SQLGenerationStatus = Field(description="SQL generation status.")
    sql: str | None = Field(default=None, description="Generated SQL text.")
    template: SQLTemplateReference | None = Field(
        default=None,
        description="Template used to generate SQL.",
    )
    reason: str | None = Field(
        default=None,
        description="Reason SQL generation was blocked or completed.",
    )
