"""SQL Generation Engine for explicitly supported report types."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from engine.requirement_engine.models import DecisionStatus
from engine.requirement_engine.models import RequirementAnalysis
from engine.sql_engine.sql_models import SQLGenerationResult, SQLGenerationStatus
from engine.sql_planner.plan_models import SQLPlan
from engine.sql_planner.sql_planner import SQLPlanner, SQLPlanningError


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

    def generate(self, source: SQLPlan | RequirementAnalysis) -> SQLGenerationResult:
        """Generate SQL from a SQLPlan, with temporary RequirementAnalysis support."""

        if isinstance(source, SQLPlan):
            return self.generate_from_plan(source)

        analysis = source

        if analysis.decision_status != DecisionStatus.SQL_ALLOWED:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                report_type=analysis.known_information.report_type,
                reason="RequirementAnalysis decision_status is not SQL_ALLOWED.",
            )

        try:
            plan = SQLPlanner().plan(analysis)
        except SQLPlanningError as exc:
            raise SQLGenerationError(str(exc)) from exc
        return self.generate_from_plan(plan)

    def generate_from_plan(self, plan: SQLPlan) -> SQLGenerationResult:
        """Generate SQL from a semantic SQLPlan."""

        report_type = plan.report_type
        if report_type == self.GARDEN_RANKING_REPORT:
            return self._generate_garden_ranking(plan)
        if report_type == self.SALE_WISE_AVERAGE_PRICE_REPORT:
            return self._generate_sale_wise_average_price(plan)
        if report_type == self.BUYER_PURCHASE_REPORT:
            return self._generate_buyer_purchase(plan)
        if report_type == self.PRICE_BAND_REPORT:
            return self._generate_price_band(plan)
        if report_type == self.COMPARISON_REPORT:
            return self._generate_comparison(plan)

        return SQLGenerationResult(
            status=SQLGenerationStatus.BLOCKED,
            report_type=report_type,
            reason="SQL generation not implemented for this report type yet.",
        )

    def _generate_garden_ranking(
        self,
        plan: SQLPlan,
    ) -> SQLGenerationResult:
        """Generate Garden Ranking SQL."""

        context = self._garden_ranking_context_from_plan(plan)
        sql = self._render_template("garden_ranking.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.GARDEN_RANKING_REPORT,
            reason="Garden Ranking SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE],
            applied_business_rules=plan.applied_business_rules,
        )

    def _generate_buyer_purchase(
        self,
        plan: SQLPlan,
    ) -> SQLGenerationResult:
        """Generate Buyer Purchase SQL."""

        context = self._buyer_purchase_context_from_plan(plan)
        sql = self._render_template("buyer_purchase.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.BUYER_PURCHASE_REPORT,
            reason="Buyer Purchase SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE, self.BUYER_GROUP_TABLE],
            applied_business_rules=plan.applied_business_rules,
        )

    def _generate_sale_wise_average_price(
        self,
        plan: SQLPlan,
    ) -> SQLGenerationResult:
        """Generate Sale Wise Average Price SQL."""

        context = self._sale_wise_average_price_context_from_plan(plan)
        sql = self._render_template("sale_wise_average_price.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.SALE_WISE_AVERAGE_PRICE_REPORT,
            reason="Sale Wise Average Price SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE],
            applied_business_rules=plan.applied_business_rules,
        )

    def _generate_price_band(
        self,
        plan: SQLPlan,
    ) -> SQLGenerationResult:
        """Generate Price Band SQL."""

        context = self._price_band_context_from_plan(plan)
        sql = self._render_template("price_band.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.PRICE_BAND_REPORT,
            reason="Price Band SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE],
            applied_business_rules=plan.applied_business_rules,
        )

    def _generate_comparison(
        self,
        plan: SQLPlan,
    ) -> SQLGenerationResult:
        """Generate buyer-wise comparison SQL."""

        context = self._comparison_context_from_plan(plan)
        sql = self._render_template("comparison_buyer_wise.sql.j2", context)

        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=self.COMPARISON_REPORT,
            reason="Comparison SQL generated.",
            warnings=[],
            source_tables=[self.SOURCE_TABLE, self.BUYER_GROUP_TABLE],
            applied_business_rules=plan.applied_business_rules,
        )

    def _garden_ranking_context_from_plan(self, plan: SQLPlan) -> dict[str, str | int]:
        """Build Garden Ranking template context from SQLPlan."""

        return {
            "source_table": plan.source_table,
            "season": self._required_filter_value(plan, "FYear"),
            "sale_filter": self._required_sale_filter(plan),
            "area_alias": self._required_filter_value(plan, "AreaAlias"),
            "category": self._required_filter_value(plan, "Category"),
            "est_blf": self._required_filter_value(plan, "EstBlf"),
        }

    def _sale_wise_average_price_context_from_plan(
        self,
        plan: SQLPlan,
    ) -> dict[str, str | int]:
        """Build Sale Wise Average Price template context from SQLPlan."""

        return {
            "source_table": plan.source_table,
            "season": self._required_filter_value(plan, "FYear"),
            "sale_filter": self._required_sale_filter(plan),
            "area_alias": self._required_filter_value(plan, "AreaAlias"),
            "category": self._required_filter_value(plan, "Category"),
        }

    def _buyer_purchase_context_from_plan(self, plan: SQLPlan) -> dict[str, str | int]:
        """Build Buyer Purchase template context from SQLPlan."""

        return {
            "source_table": plan.source_table,
            "buyer_group_table": self.BUYER_GROUP_TABLE,
            "season": self._required_filter_value(plan, "FYear"),
            "sale_filter": self._required_sale_filter(plan),
            "category": self._required_filter_value(plan, "Category"),
            "buyer_group": self._required_filter_value(plan, "BuyerMDM"),
        }

    def _price_band_context_from_plan(self, plan: SQLPlan) -> dict[str, str | int]:
        """Build Price Band template context from SQLPlan."""

        return {
            "source_table": plan.source_table,
            "season": self._required_filter_value(plan, "FYear"),
            "sale_filter": self._required_sale_filter(plan),
            "area_alias": self._required_filter_value(plan, "AreaAlias"),
            "category": self._required_filter_value(plan, "Category"),
        }

    def _comparison_context_from_plan(self, plan: SQLPlan) -> dict[str, str | int]:
        """Build Comparison template context from SQLPlan."""

        return {
            "source_table": plan.source_table,
            "buyer_group_table": self.BUYER_GROUP_TABLE,
            "season_list": self._required_fyear_in(plan),
            "sale_filter": self._required_sale_filter(plan),
            "category": self._required_filter_value(plan, "Category"),
            "buyer_group": self._required_filter_value(plan, "BuyerMDM"),
        }

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

    @staticmethod
    def _required_filter_value(plan: SQLPlan, field_name: str) -> str:
        """Return a semantic equality filter value from a SQLPlan."""

        pattern = re.compile(rf"^{re.escape(field_name)}\s*=\s*(.+)$", re.IGNORECASE)
        for filter_text in plan.filters:
            match = pattern.match(filter_text)
            if match:
                return match.group(1).strip()
        raise SQLGenerationError(
            f"Cannot generate {plan.report_type} SQL. Missing plan filter: {field_name}"
        )

    @staticmethod
    def _required_sale_filter(plan: SQLPlan) -> str:
        """Return the SaleAlias predicate from a SQLPlan."""

        for filter_text in plan.filters:
            if re.match(r"^SaleAlias\s+(BETWEEN|=)", filter_text, re.IGNORECASE):
                return filter_text
        raise SQLGenerationError(
            f"Cannot generate {plan.report_type} SQL. Missing plan filter: SaleAlias"
        )

    @staticmethod
    def _required_fyear_in(plan: SQLPlan) -> str:
        """Return the comma-separated FYear IN values from a SQLPlan."""

        pattern = re.compile(r"^FYear\s+IN\s*\(([^)]*)\)$", re.IGNORECASE)
        for filter_text in plan.filters:
            match = pattern.match(filter_text)
            if match:
                return match.group(1).strip()
        raise SQLGenerationError(
            f"Cannot generate {plan.report_type} SQL. Missing plan filter: FYear IN"
        )

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
