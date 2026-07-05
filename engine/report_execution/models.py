"""Models for report execution results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReportExecutionStatus(str, Enum):
    """Lifecycle status for executable report generation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ReportExecutionResult(BaseModel):
    """Structured result returned by the ReportExecutionEngine."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    status: ReportExecutionStatus = Field(description="Execution status.")
    output_file: str | None = Field(default=None, description="Generated Excel file.")
    row_count: int | None = Field(default=None, ge=0, description="Rows returned.")
    execution_time: float | None = Field(
        default=None,
        ge=0.0,
        description="Elapsed execution time in seconds.",
    )
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = Field(default=None)

