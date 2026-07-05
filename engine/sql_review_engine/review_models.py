"""Data models for SQL review results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SQLReviewStatus(str, Enum):
    """Overall SQL review status."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class SQLReviewResult(BaseModel):
    """Structured result returned by the SQL Review Engine."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    status: SQLReviewStatus = Field(description="Overall review status.")
    issues: list[str] = Field(default_factory=list, description="Critical issues.")
    warnings: list[str] = Field(default_factory=list, description="Non-critical warnings.")
    passed_checks: list[str] = Field(default_factory=list, description="Checks that passed.")
    failed_checks: list[str] = Field(default_factory=list, description="Checks that failed.")
    review_summary: str = Field(description="Human-readable review summary.")
    confidence: float = Field(ge=0.0, le=1.0, description="Reviewer confidence score.")

