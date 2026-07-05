"""Report output filename builder."""

from __future__ import annotations

import re

from engine.sql_planner.plan_models import SQLPlan


class ReportFilenameBuilder:
    """Build deterministic Excel filenames from SQLPlan filters."""

    GARDEN_RANKING_REPORT = "Garden Ranking Report"
    SALE_WISE_AVERAGE_PRICE_REPORT = "Sale Wise Average Price Report"
    BUYER_PURCHASE_REPORT = "Buyer Purchase Report"
    PRICE_BAND_REPORT = "Price Band Report"
    COMPARISON_REPORT = "Comparison Report"

    PREFIXES = {
        GARDEN_RANKING_REPORT: "Garden_Ranking",
        SALE_WISE_AVERAGE_PRICE_REPORT: "Sale_Wise_Average",
        BUYER_PURCHASE_REPORT: "Buyer_Purchase",
        PRICE_BAND_REPORT: "Price_Band",
        COMPARISON_REPORT: "Comparison",
    }

    BUYER_ALIASES = {
        "HINDUSTHAN UNILEVER LIMITED": "HUL",
        "TATA CONSUMER PRODUCTS LTD.": "TCPL",
    }

    def build(self, plan: SQLPlan) -> str:
        """Return a report-specific Excel filename."""

        prefix = self.PREFIXES.get(plan.report_type, self._safe_token(plan.report_type))
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

