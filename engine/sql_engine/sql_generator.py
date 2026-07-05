"""SQL Generation Engine backed by SQLPlan and Jinja2 templates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from engine.requirement_engine.models import DecisionStatus, RequirementAnalysis
from engine.sql_engine.sql_models import SQLGenerationResult, SQLGenerationStatus
from engine.sql_engine.template_renderer import SQLTemplateRenderer
from engine.sql_planner.plan_models import SQLPlan
from engine.sql_planner.sql_planner import SQLPlanner, SQLPlanningError


class SQLGenerationError(ValueError):
    """Raised when SQL generation is requested with invalid inputs."""


@dataclass(frozen=True, slots=True)
class ReportTemplate:
    """Template metadata for one supported report type."""

    template_name: str
    source_tables: list[str]


class SQLGenerator:
    """Render SQL for supported report types from semantic SQL plans."""

    GARDEN_RANKING_REPORT = "Garden Ranking Report"
    SALE_WISE_AVERAGE_PRICE_REPORT = "Sale Wise Average Price Report"
    BUYER_PURCHASE_REPORT = "Buyer Purchase Report"
    PRICE_BAND_REPORT = "Price Band Report"
    COMPARISON_REPORT = "Comparison Report"

    SOURCE_TABLE = "data-warehousing-prod.EasyReports.SaleTransactionView"
    BUYER_GROUP_TABLE = "data-warehousing-prod.EasyReports.Parcon-BuyerGroup"

    REPORT_TEMPLATES = {
        GARDEN_RANKING_REPORT: ReportTemplate(
            template_name="garden_ranking.sql.j2",
            source_tables=[SOURCE_TABLE],
        ),
        SALE_WISE_AVERAGE_PRICE_REPORT: ReportTemplate(
            template_name="sale_wise_average.sql.j2",
            source_tables=[SOURCE_TABLE],
        ),
        BUYER_PURCHASE_REPORT: ReportTemplate(
            template_name="buyer_purchase.sql.j2",
            source_tables=[SOURCE_TABLE, BUYER_GROUP_TABLE],
        ),
        PRICE_BAND_REPORT: ReportTemplate(
            template_name="price_band.sql.j2",
            source_tables=[SOURCE_TABLE],
        ),
        COMPARISON_REPORT: ReportTemplate(
            template_name="comparison.sql.j2",
            source_tables=[SOURCE_TABLE, BUYER_GROUP_TABLE],
        ),
    }

    def __init__(self, renderer: SQLTemplateRenderer | None = None) -> None:
        """Create a SQL generator with an injectable template renderer."""

        self.renderer = renderer or SQLTemplateRenderer()

    def generate(self, source: SQLPlan | RequirementAnalysis) -> SQLGenerationResult:
        """Generate SQL from a SQLPlan, with temporary RequirementAnalysis support."""

        if isinstance(source, SQLPlan):
            return self.generate_from_plan(source)

        if source.decision_status != DecisionStatus.SQL_ALLOWED:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                report_type=source.known_information.report_type,
                reason="RequirementAnalysis decision_status is not SQL_ALLOWED.",
            )

        try:
            plan = SQLPlanner().plan(source)
        except SQLPlanningError as exc:
            raise SQLGenerationError(str(exc)) from exc
        return self.generate_from_plan(plan)

    def generate_from_plan(self, plan: SQLPlan) -> SQLGenerationResult:
        """Generate SQL from a semantic SQLPlan."""

        template = self.REPORT_TEMPLATES.get(plan.report_type)
        if template is None:
            return SQLGenerationResult(
                status=SQLGenerationStatus.BLOCKED,
                report_type=plan.report_type,
                reason="SQL generation not implemented for this report type yet.",
            )

        context = self._context_from_plan(plan)
        sql = self.renderer.render(template.template_name, context)
        return SQLGenerationResult(
            status=SQLGenerationStatus.GENERATED,
            sql=sql,
            report_type=plan.report_type,
            reason=f"{plan.report_type} SQL generated.",
            warnings=[],
            source_tables=template.source_tables,
            applied_business_rules=plan.applied_business_rules,
        )

    def _context_from_plan(self, plan: SQLPlan) -> dict[str, Any]:
        """Build render context from a SQLPlan."""

        context: dict[str, Any] = {
            "source_table": plan.source_table,
            "sale_filter": self._required_sale_filter(plan),
            "category": self._required_filter_value(plan, "Category"),
        }

        if plan.report_type == self.COMPARISON_REPORT:
            context["season_list"] = self._required_fyear_in(plan)
        else:
            context["season"] = self._required_filter_value(plan, "FYear")

        if self._needs_area_alias(plan):
            context["area_alias"] = self._required_filter_value(plan, "AreaAlias")
        if plan.report_type == self.GARDEN_RANKING_REPORT:
            context["est_blf"] = self._required_filter_value(plan, "EstBlf")
        if plan.report_type in {self.BUYER_PURCHASE_REPORT, self.COMPARISON_REPORT}:
            context["buyer_group_table"] = self.BUYER_GROUP_TABLE
            context["buyer_group"] = self._required_filter_value(plan, "BuyerMDM")

        return context

    def get_template_name(self, report_type: str) -> str | None:
        """Return the template selected for a report type."""

        template = self.REPORT_TEMPLATES.get(report_type)
        return template.template_name if template else None

    @classmethod
    def _needs_area_alias(cls, plan: SQLPlan) -> bool:
        """Return whether a report template requires AreaAlias."""

        return plan.report_type in {
            cls.GARDEN_RANKING_REPORT,
            cls.SALE_WISE_AVERAGE_PRICE_REPORT,
            cls.PRICE_BAND_REPORT,
        }

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
