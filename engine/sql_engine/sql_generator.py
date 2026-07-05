"""SQL generator scaffold.

This module intentionally does not generate SQL yet. It exists as the boundary
for the future SQL Generation Engine.
"""

from __future__ import annotations

from engine.requirement_engine.models import RequirementAnalysis
from engine.sql_engine.sql_models import SQLGenerationResult, SQLGenerationStatus


class SQLGenerator:
    """Generate SQL only after requirement analysis explicitly allows it."""

    def generate(self, analysis: RequirementAnalysis) -> SQLGenerationResult:
        """Return a blocked result until SQL generation logic is implemented."""

        if not analysis.sql_generation_allowed:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                reason="Requirement analysis has not allowed SQL generation.",
            )

        return SQLGenerationResult(
            status=SQLGenerationStatus.BLOCKED,
            reason="SQL generation is not implemented yet.",
        )
