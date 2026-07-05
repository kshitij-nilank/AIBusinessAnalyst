"""SQL Generation Engine v1 for Garden Ranking Report only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from engine.requirement_engine.models import DecisionStatus
from engine.requirement_engine.models import RequirementAnalysis
from engine.sql_engine.sql_models import SQLGenerationResult, SQLGenerationStatus


class SQLGenerationError(ValueError):
    """Raised when SQL generation is requested with invalid inputs."""


@dataclass(frozen=True, slots=True)
class SaleRange:
    """Normalized sale range for SQL filtering."""

    start: int
    end: int


class SQLGenerator:
    """Generate SQL for Garden Ranking Report only."""

    SUPPORTED_REPORT_TYPE = "Garden Ranking Report"
    SOURCE_TABLE = "data-warehousing-prod.EasyReports.SaleTransactionView"

    def generate(self, analysis: RequirementAnalysis) -> SQLGenerationResult:
        """Generate Garden Ranking SQL for an allowed requirement analysis."""

        if analysis.decision_status != DecisionStatus.SQL_ALLOWED:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                report_type=analysis.known_information.report_type,
                reason="RequirementAnalysis decision_status is not SQL_ALLOWED.",
            )

        if analysis.known_information.report_type != self.SUPPORTED_REPORT_TYPE:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                report_type=analysis.known_information.report_type,
                reason="SQL generation not implemented for this report type yet.",
            )

        context = self._build_context(analysis)
        sql = self._render_template(context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.SUPPORTED_REPORT_TYPE,
            reason="Garden Ranking SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE],
            applied_business_rules=[
                "BR-001 FYear",
                "BR-002 SaleAlias",
                "BR-003 AreaAlias",
                "BR-009 EstBlf",
                "BR-017 GardenRanking",
            ],
        )

    def _build_context(self, analysis: RequirementAnalysis) -> dict[str, str | int]:
        """Validate Garden Ranking inputs and build template context."""

        known = analysis.known_information
        season = known.season or (known.seasons[0] if known.seasons else None)
        sale_range = self._parse_sale_range(known.sale_range)

        required_values = {
            "season": season,
            "sale_range": known.sale_range,
            "area": known.area,
            "category": known.category,
            "est_blf": known.est_blf,
            "output_grain": known.output_grain,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise SQLGenerationError(
                "Cannot generate Garden Ranking SQL. Missing required field(s): "
                + ", ".join(missing)
            )

        metrics = {metric.casefold() for metric in known.metrics}
        if "ranking" not in metrics:
            raise SQLGenerationError(
                "Cannot generate Garden Ranking SQL. Required metric is ranking."
            )
        if known.output_grain != "garden-wise":
            raise SQLGenerationError(
                "Cannot generate Garden Ranking SQL. Grouping must be garden-wise."
            )

        return {
            "source_table": self.SOURCE_TABLE,
            "season": int(season),
            "sale_filter": self._sale_filter(sale_range),
            "area_alias": known.area,
            "category": known.category,
            "est_blf": known.est_blf,
        }

    @staticmethod
    def _parse_sale_range(value: str | None) -> SaleRange:
        """Parse supported sale range text into numeric bounds."""

        if not value:
            raise SQLGenerationError(
                "Cannot generate Garden Ranking SQL. Missing required field: sale_range"
            )

        normalized = value.casefold().replace("up to", "upto")
        range_match = re.search(r"sale\s+range\s+(\d+)\s+to\s+(\d+)", normalized)
        if not range_match:
            range_match = re.search(r"sale\s+(\d+)\s*(?:to|-)\s*(\d+)", normalized)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            return SaleRange(start=min(start, end), end=max(start, end))

        upto_match = re.search(r"upto\s+sale\s+(\d+)", normalized)
        if upto_match:
            return SaleRange(start=14, end=int(upto_match.group(1)))

        single_match = re.search(r"sale\s+(\d+)", normalized)
        if single_match:
            sale_no = int(single_match.group(1))
            return SaleRange(start=sale_no, end=sale_no)

        raise SQLGenerationError(
            "Cannot generate Garden Ranking SQL. Unsupported sale range format."
        )

    @staticmethod
    def _sale_filter(sale_range: SaleRange) -> str:
        """Return SQL predicate for the normalized sale range."""

        if sale_range.start == sale_range.end:
            return f"SaleAlias = {sale_range.start}"
        return f"SaleAlias BETWEEN {sale_range.start} AND {sale_range.end}"

    def _render_template(self, context: dict[str, str | int]) -> str:
        """Render the Garden Ranking SQL template using simple placeholders."""

        template = self._template_path().read_text(encoding="utf-8")
        sql = template
        for key, value in context.items():
            sql = sql.replace("{{ " + key + " }}", str(value))
        return sql.strip()

    @staticmethod
    def _template_path() -> Path:
        """Return the Garden Ranking SQL template path."""

        return Path(__file__).resolve().parent / "templates" / "garden_ranking.sql.j2"
