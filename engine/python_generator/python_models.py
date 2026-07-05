"""Data models for generated Python report scripts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PythonGenerationStatus(str, Enum):
    """Lifecycle status for Python script generation."""

    GENERATED = "GENERATED"
    BLOCKED = "BLOCKED"


class PythonGenerationResult(BaseModel):
    """Structured result returned by the Python generator."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    status: PythonGenerationStatus = Field(description="Generation status.")
    report_type: str = Field(description="Report type for the generated script.")
    script: str | None = Field(default=None, description="Generated Python script text.")
    output_filename: str | None = Field(
        default=None,
        description="Excel output filename used by the generated script.",
    )
    reason: str | None = Field(
        default=None,
        description="Reason generation was blocked or completed.",
    )
    warnings: list[str] = Field(default_factory=list)

