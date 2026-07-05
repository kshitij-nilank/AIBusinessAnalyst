"""SQL Generation Engine for explicitly supported report types."""

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
    """Generate SQL for explicitly supported report types."""

    GARDEN_RANKING_REPORT = "Garden Ranking Report"
    SALE_WISE_AVERAGE_PRICE_REPORT = "Sale Wise Average Price Report"
    BUYER_PURCHASE_REPORT = "Buyer Purchase Report"
    PRICE_BAND_REPORT = "Price Band Report"
    COMPARISON_REPORT = "Comparison Report"
    SOURCE_TABLE = "data-warehousing-prod.EasyReports.SaleTransactionView"
    BUYER_GROUP_TABLE = "data-warehousing-prod.EasyReports.Parcon-BuyerGroup"
    BUYER_MAPPING = {
        "HUL": "HINDUSTHAN UNILEVER LIMITED",
        "TCPL": "TATA CONSUMER PRODUCTS LTD.",
    }

    def generate(self, analysis: RequirementAnalysis) -> SQLGenerationResult:
        """Generate SQL for a supported, allowed requirement analysis."""

        if analysis.decision_status != DecisionStatus.SQL_ALLOWED:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                report_type=analysis.known_information.report_type,
                reason="RequirementAnalysis decision_status is not SQL_ALLOWED.",
            )

        report_type = analysis.known_information.report_type
        if report_type == self.GARDEN_RANKING_REPORT:
            return self._generate_garden_ranking(analysis)
        if report_type == self.SALE_WISE_AVERAGE_PRICE_REPORT:
            return self._generate_sale_wise_average_price(analysis)
        if report_type == self.BUYER_PURCHASE_REPORT:
            return self._generate_buyer_purchase(analysis)
        if report_type == self.PRICE_BAND_REPORT:
            return self._generate_price_band(analysis)
        if report_type == self.COMPARISON_REPORT:
            return self._generate_comparison(analysis)

        return SQLGenerationResult(
            status=SQLGenerationStatus.BLOCKED,
            report_type=report_type,
            reason="SQL generation not implemented for this report type yet.",
        )

    def _generate_garden_ranking(
        self,
        analysis: RequirementAnalysis,
    ) -> SQLGenerationResult:
        """Generate Garden Ranking SQL."""

        context = self._build_garden_ranking_context(analysis)
        sql = self._render_template("garden_ranking.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.GARDEN_RANKING_REPORT,
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

    def _generate_buyer_purchase(
        self,
        analysis: RequirementAnalysis,
    ) -> SQLGenerationResult:
        """Generate Buyer Purchase SQL."""

        context = self._build_buyer_purchase_context(analysis)
        sql = self._render_template("buyer_purchase.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.BUYER_PURCHASE_REPORT,
            reason="Buyer Purchase SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE, self.BUYER_GROUP_TABLE],
            applied_business_rules=[
                "BR-001 FYear",
                "BR-002 SaleAlias",
                "BR-015 BuyerGroup",
            ],
        )

    def _generate_sale_wise_average_price(
        self,
        analysis: RequirementAnalysis,
    ) -> SQLGenerationResult:
        """Generate Sale Wise Average Price SQL."""

        context = self._build_sale_wise_average_price_context(analysis)
        sql = self._render_template("sale_wise_average_price.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.SALE_WISE_AVERAGE_PRICE_REPORT,
            reason="Sale Wise Average Price SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE],
            applied_business_rules=[
                "BR-001 FYear",
                "BR-002 SaleAlias",
                "BR-003 AreaAlias",
                "BR-006 AveragePrice",
            ],
        )

    def _generate_price_band(
        self,
        analysis: RequirementAnalysis,
    ) -> SQLGenerationResult:
        """Generate Price Band SQL."""

        context = self._build_price_band_context(analysis)
        sql = self._render_template("price_band.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.PRICE_BAND_REPORT,
            reason="Price Band SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE],
            applied_business_rules=[
                "BR-001 FYear",
                "BR-002 SaleAlias",
                "BR-003 AreaAlias",
                "BR-007 PriceBands",
            ],
        )

    def _generate_comparison(
        self,
        analysis: RequirementAnalysis,
    ) -> SQLGenerationResult:
        """Generate buyer-wise comparison SQL."""

        context = self._build_comparison_context(analysis)
        sql = self._render_template("comparison_buyer_wise.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.COMPARISON_REPORT,
            reason="Comparison SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE, self.BUYER_GROUP_TABLE],
            applied_business_rules=[
                "BR-001 FYear",
                "BR-002 SaleAlias",
                "BR-015 BuyerGroup",
                "BR-027 HistoricalComparison",
            ],
        )

    def _build_garden_ranking_context(
        self,
        analysis: RequirementAnalysis,
    ) -> dict[str, str | int]:
        """Validate Garden Ranking inputs and build template context."""

        context = self._base_context(analysis, report_name="Garden Ranking")
        known = analysis.known_information
        if not known.est_blf:
            raise SQLGenerationError(
                "Cannot generate Garden Ranking SQL. Missing required field(s): est_blf"
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

        context["est_blf"] = known.est_blf
        return context

    def _build_sale_wise_average_price_context(
        self,
        analysis: RequirementAnalysis,
    ) -> dict[str, str | int]:
        """Validate Sale Wise Average Price inputs and build template context."""

        context = self._base_context(
            analysis,
            report_name="Sale Wise Average Price",
        )
        known = analysis.known_information
        metrics = {metric.casefold() for metric in known.metrics}
        if "average price" not in metrics:
            raise SQLGenerationError(
                "Cannot generate Sale Wise Average Price SQL. Required metric is average price."
            )
        if known.output_grain != "sale-wise":
            raise SQLGenerationError(
                "Cannot generate Sale Wise Average Price SQL. Grouping must be sale-wise."
            )

        return context

    def _build_buyer_purchase_context(
        self,
        analysis: RequirementAnalysis,
    ) -> dict[str, str | int]:
        """Validate Buyer Purchase inputs and build template context."""

        known = analysis.known_information
        season = known.season or (known.seasons[0] if known.seasons else None)
        sale_range = self._parse_sale_range(known.sale_range)
        buyer_group = self._buyer_group_name(known.buyer)

        required_values = {
            "season": season,
            "sale_range": known.sale_range,
            "buyer": buyer_group,
            "category": known.category,
            "output_grain": known.output_grain,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise SQLGenerationError(
                "Cannot generate Buyer Purchase SQL. Missing required field(s): "
                + ", ".join(missing)
            )

        metrics = {metric.casefold() for metric in known.metrics}
        if not {"quantity", "value"}.issubset(metrics):
            raise SQLGenerationError(
                "Cannot generate Buyer Purchase SQL. Required metrics are quantity and value."
            )
        if known.output_grain != "buyer-wise":
            raise SQLGenerationError(
                "Cannot generate Buyer Purchase SQL. Grouping must be buyer-wise."
            )

        return {
            "source_table": self.SOURCE_TABLE,
            "buyer_group_table": self.BUYER_GROUP_TABLE,
            "season": int(season),
            "sale_filter": self._sale_filter(sale_range),
            "category": known.category,
            "buyer_group": buyer_group,
        }

    def _build_price_band_context(
        self,
        analysis: RequirementAnalysis,
    ) -> dict[str, str | int]:
        """Validate Price Band inputs and build template context."""

        context = self._base_context(analysis, report_name="Price Band")
        known = analysis.known_information
        metrics = {metric.casefold() for metric in known.metrics}
        if "price band analysis" not in metrics:
            raise SQLGenerationError(
                "Cannot generate Price Band SQL. Required metric is price band analysis."
            )
        if known.output_grain != "garden-wise":
            raise SQLGenerationError(
                "Cannot generate Price Band SQL. Grouping must be garden-wise."
            )

        context["area_alias"] = self._sql_area_alias(str(context["area_alias"]))
        return context

    def _build_comparison_context(
        self,
        analysis: RequirementAnalysis,
    ) -> dict[str, str | int]:
        """Validate buyer-wise comparison inputs and build template context."""

        known = analysis.known_information
        seasons = list(dict.fromkeys(known.seasons))
        sale_range = self._parse_sale_range(known.sale_range)
        buyer_group = self._buyer_group_name(known.buyer)

        required_values = {
            "seasons": seasons if len(seasons) >= 2 else None,
            "sale_range": known.sale_range,
            "buyer": buyer_group,
            "category": known.category,
            "output_grain": known.output_grain,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise SQLGenerationError(
                "Cannot generate Comparison SQL. Missing required field(s): "
                + ", ".join(missing)
            )

        metrics = {metric.casefold() for metric in known.metrics}
        if not {"quantity", "value"}.issubset(metrics):
            raise SQLGenerationError(
                "Cannot generate Comparison SQL. Required metrics are quantity and value."
            )
        if known.output_grain != "buyer-wise":
            raise SQLGenerationError(
                "Cannot generate Comparison SQL. Grouping must be buyer-wise."
            )

        return {
            "source_table": self.SOURCE_TABLE,
            "buyer_group_table": self.BUYER_GROUP_TABLE,
            "season_list": ", ".join(str(season) for season in seasons[:2]),
            "sale_filter": self._sale_filter(sale_range),
            "category": known.category,
            "buyer_group": buyer_group,
        }

    def _base_context(
        self,
        analysis: RequirementAnalysis,
        *,
        report_name: str,
    ) -> dict[str, str | int]:
        """Validate common required fields and build shared template context."""

        known = analysis.known_information
        season = known.season or (known.seasons[0] if known.seasons else None)
        sale_range = self._parse_sale_range(known.sale_range)

        required_values = {
            "season": season,
            "sale_range": known.sale_range,
            "area": known.area,
            "category": known.category,
            "output_grain": known.output_grain,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise SQLGenerationError(
                f"Cannot generate {report_name} SQL. Missing required field(s): "
                + ", ".join(missing)
            )

        return {
            "source_table": self.SOURCE_TABLE,
            "season": int(season),
            "sale_filter": self._sale_filter(sale_range),
            "area_alias": known.area,
            "category": known.category,
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

    @classmethod
    def _buyer_group_name(cls, buyer: str | None) -> str | None:
        """Return canonical buyer group name for supported buyer aliases."""

        if not buyer:
            return None
        normalized = buyer.strip().upper()
        if normalized in cls.BUYER_MAPPING:
            return cls.BUYER_MAPPING[normalized]
        if normalized in cls.BUYER_MAPPING.values():
            return normalized
        return buyer.strip()

    @staticmethod
    def _sql_area_alias(area: str) -> str:
        """Return SQL AreaAlias value for area-level filters."""

        if area == "DO":
            return "DO/TR"
        if area == "CA":
            return "CA/TP"
        return area

    def _render_template(
        self,
        template_name: str,
        context: dict[str, str | int],
    ) -> str:
        """Render a SQL template using simple placeholders."""

        template = self._template_path(template_name).read_text(encoding="utf-8")
        sql = template
        for key, value in context.items():
            sql = sql.replace("{{ " + key + " }}", str(value))
        return sql.strip()

    @staticmethod
    def _template_path(template_name: str) -> Path:
        """Return a SQL template path."""

        return Path(__file__).resolve().parent / "templates" / template_name
