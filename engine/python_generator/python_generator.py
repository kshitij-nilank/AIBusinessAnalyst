"""Python Report Generation Engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from engine.python_generator.python_models import (
    PythonGenerationResult,
    PythonGenerationStatus,
)
from engine.python_generator.python_template_renderer import PythonTemplateRenderer
from engine.sql_planner.plan_models import SQLPlan
from engine.sql_review_engine.review_models import SQLReviewResult, SQLReviewStatus


@dataclass(frozen=True, slots=True)
class PythonTemplate:
    """Template metadata for one supported report script."""

    template_name: str
    filename_prefix: str


class PythonGenerator:
    """Generate Python report scripts from SQLPlan and reviewed SQL."""

    GARDEN_RANKING_REPORT = "Garden Ranking Report"
    SALE_WISE_AVERAGE_PRICE_REPORT = "Sale Wise Average Price Report"
    BUYER_PURCHASE_REPORT = "Buyer Purchase Report"
    PRICE_BAND_REPORT = "Price Band Report"
    COMPARISON_REPORT = "Comparison Report"

    REPORT_TEMPLATES = {
        GARDEN_RANKING_REPORT: PythonTemplate(
            template_name="garden_ranking.py.j2",
            filename_prefix="Garden_Ranking",
        ),
        SALE_WISE_AVERAGE_PRICE_REPORT: PythonTemplate(
            template_name="sale_wise_average.py.j2",
            filename_prefix="Sale_Wise_Average",
        ),
        BUYER_PURCHASE_REPORT: PythonTemplate(
            template_name="buyer_purchase.py.j2",
            filename_prefix="Buyer_Purchase",
        ),
        PRICE_BAND_REPORT: PythonTemplate(
            template_name="price_band.py.j2",
            filename_prefix="Price_Band",
        ),
        COMPARISON_REPORT: PythonTemplate(
            template_name="comparison.py.j2",
            filename_prefix="Comparison",
        ),
    }

    BUYER_ALIASES = {
        "HINDUSTHAN UNILEVER LIMITED": "HUL",
        "TATA CONSUMER PRODUCTS LTD.": "TCPL",
    }

    def __init__(self, renderer: PythonTemplateRenderer | None = None) -> None:
        """Create a Python generator with an injectable renderer."""

        self.renderer = renderer or PythonTemplateRenderer()

    def generate(
        self,
        *,
        plan: SQLPlan,
        sql: str,
        review_result: SQLReviewResult,
    ) -> PythonGenerationResult:
        """Generate a Python report script as text."""

        if review_result.status != SQLReviewStatus.PASS:
            return PythonGenerationResult(
                status=PythonGenerationStatus.BLOCKED,
                report_type=plan.report_type,
                reason="Python generation blocked because SQL review did not pass.",
                warnings=list(review_result.warnings),
            )

        template = self.REPORT_TEMPLATES.get(plan.report_type)
        if template is None:
            return PythonGenerationResult(
                status=PythonGenerationStatus.BLOCKED,
                report_type=plan.report_type,
                reason="Python generation is not implemented for this report type.",
            )

        output_filename = self._output_filename(plan, template.filename_prefix)
        script = self.renderer.render(
            template.template_name,
            {
                "report_title": plan.report_type,
                "sql": sql,
                "output_filename": output_filename,
            },
        )
        return PythonGenerationResult(
            status=PythonGenerationStatus.GENERATED,
            report_type=plan.report_type,
            script=script,
            output_filename=output_filename,
            reason="Python report script generated.",
            warnings=list(plan.warnings),
        )

    def get_template_name(self, report_type: str) -> str | None:
        """Return the Python template selected for a report type."""

        template = self.REPORT_TEMPLATES.get(report_type)
        return template.template_name if template else None

    def _output_filename(self, plan: SQLPlan, prefix: str) -> str:
        """Return a deterministic report-specific Excel filename."""

        buyer = self._filter_value(plan, "BuyerMDM")
        seasons = self._season_tokens(plan)
        sale = self._sale_token(plan)

        if plan.report_type == self.PRICE_BAND_REPORT:
            area = self._filter_value(plan, "AreaAlias")
            parts = [prefix, self._safe_token(area) if area else "Unknown_Area"]
            parts.extend(seasons)
        elif buyer:
            parts = [prefix, self.BUYER_ALIASES.get(buyer, self._safe_token(buyer))]
            parts.extend(seasons)
        else:
            parts = [prefix]
            parts.extend(seasons)

        if sale:
            parts.append(sale)

        return "_".join(part for part in parts if part) + ".xlsx"

    @staticmethod
    def _filter_value(plan: SQLPlan, field_name: str) -> str | None:
        """Return an equality filter value from a SQLPlan."""

        pattern = re.compile(rf"^{re.escape(field_name)}\s*=\s*(.+)$", re.IGNORECASE)
        for filter_text in plan.filters:
            match = pattern.match(filter_text)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _season_tokens(plan: SQLPlan) -> list[str]:
        """Return filename tokens for FYear filters."""

        for filter_text in plan.filters:
            match = re.match(r"^FYear\s*=\s*(\d{4})$", filter_text, re.IGNORECASE)
            if match:
                return [match.group(1)]
            in_match = re.match(
                r"^FYear\s+IN\s*\(([^)]*)\)$",
                filter_text,
                re.IGNORECASE,
            )
            if in_match:
                seasons = [
                    value.strip()
                    for value in in_match.group(1).split(",")
                    if value.strip()
                ]
                if len(seasons) >= 2:
                    return [f"{seasons[0]}_vs_{seasons[1]}"]
        return ["Unknown_Season"]

    @classmethod
    def _sale_token(cls, plan: SQLPlan) -> str | None:
        """Return filename token for the SaleAlias filter."""

        for filter_text in plan.filters:
            between = re.match(
                r"^SaleAlias\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)$",
                filter_text,
                re.IGNORECASE,
            )
            if between:
                start, end = between.group(1), between.group(2)
                if start == "14" and plan.report_type in {
                    cls.GARDEN_RANKING_REPORT,
                    cls.COMPARISON_REPORT,
                }:
                    return f"Upto_Sale_{end}"
                return f"Sale_{start}_to_{end}"

            equals = re.match(r"^SaleAlias\s*=\s*(\d+)$", filter_text, re.IGNORECASE)
            if equals:
                return f"Sale_{equals.group(1)}"
        return None

    @staticmethod
    def _safe_token(value: str) -> str:
        """Return a filesystem-friendly filename token."""

        token = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
        return token.strip("_") or "Unknown"
