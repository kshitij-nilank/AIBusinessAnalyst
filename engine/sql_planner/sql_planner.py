"""Semantic SQL Planner v1."""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.requirement_engine.models import DecisionStatus, RequirementAnalysis
from engine.sql_planner.plan_models import SQLPlan


class SQLPlanningError(ValueError):
    """Raised when a SQL plan cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class SaleRange:
    """Normalized sale range for planning."""

    start: int
    end: int


class SQLPlanner:
    """Convert allowed RequirementAnalysis objects into reusable SQLPlan objects."""

    SOURCE_TABLE = "data-warehousing-prod.EasyReports.SaleTransactionView"
    BUYER_GROUP_TABLE = "data-warehousing-prod.EasyReports.Parcon-BuyerGroup"

    GARDEN_RANKING_REPORT = "Garden Ranking Report"
    SALE_WISE_AVERAGE_PRICE_REPORT = "Sale Wise Average Price Report"
    BUYER_PURCHASE_REPORT = "Buyer Purchase Report"
    PRICE_BAND_REPORT = "Price Band Report"
    COMPARISON_REPORT = "Comparison Report"

    BUYER_MAPPING = {
        "HUL": "HINDUSTHAN UNILEVER LIMITED",
        "TCPL": "TATA CONSUMER PRODUCTS LTD.",
    }

    def plan(self, analysis: RequirementAnalysis) -> SQLPlan:
        """Return a structured SQLPlan for a supported allowed requirement."""

        if analysis.decision_status != DecisionStatus.SQL_ALLOWED:
            raise SQLPlanningError("SQL planning requires decision_status SQL_ALLOWED.")

        report_type = analysis.known_information.report_type
        if report_type == self.GARDEN_RANKING_REPORT:
            return self._garden_ranking_plan(analysis)
        if report_type == self.SALE_WISE_AVERAGE_PRICE_REPORT:
            return self._sale_wise_average_price_plan(analysis)
        if report_type == self.BUYER_PURCHASE_REPORT:
            return self._buyer_purchase_plan(analysis)
        if report_type == self.PRICE_BAND_REPORT:
            return self._price_band_plan(analysis)
        if report_type == self.COMPARISON_REPORT:
            return self._comparison_plan(analysis)

        raise SQLPlanningError(f"SQL planning is not implemented for {report_type}.")

    def _garden_ranking_plan(self, analysis: RequirementAnalysis) -> SQLPlan:
        """Build a Garden Ranking SQL plan."""

        known = analysis.known_information
        season = self._single_season(analysis)
        sale_range = self._sale_range(known.sale_range)
        self._require_fields(
            "Garden Ranking",
            {
                "area": known.area,
                "category": known.category,
                "est_blf": known.est_blf,
                "output_grain": known.output_grain,
            },
        )

        return SQLPlan(
            report_type=self.GARDEN_RANKING_REPORT,
            source_table=self.SOURCE_TABLE,
            filters=[
                f"FYear = {season}",
                self._sale_filter(sale_range),
                f"AreaAlias = {known.area}",
                f"Category = {known.category}",
                f"EstBlf = {known.est_blf}",
            ],
            group_by=["GardenMDM"],
            aggregations=[
                "Sold_Qty = SUM(TotalWeight)",
                "Total_Value = SUM(Value)",
            ],
            calculations=[
                "Avg_Price = SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))",
            ],
            ranking=["DENSE_RANK over Avg_Price desc"],
            order_by=["Rank", "GardenMDM"],
            applied_business_rules=self._business_rules(
                analysis,
                ["BR-001 FYear", "BR-002 SaleAlias", "BR-003 AreaAlias", "BR-009 EstBlf", "BR-017 GardenRanking"],
            ),
        )

    def _sale_wise_average_price_plan(
        self,
        analysis: RequirementAnalysis,
    ) -> SQLPlan:
        """Build a Sale Wise Average Price SQL plan."""

        known = analysis.known_information
        season = self._single_season(analysis)
        sale_range = self._sale_range(known.sale_range)
        self._require_fields(
            "Sale Wise Average Price",
            {
                "area": known.area,
                "category": known.category,
                "output_grain": known.output_grain,
            },
        )

        return SQLPlan(
            report_type=self.SALE_WISE_AVERAGE_PRICE_REPORT,
            source_table=self.SOURCE_TABLE,
            filters=[
                f"FYear = {season}",
                self._sale_filter(sale_range),
                f"AreaAlias = {known.area}",
                f"Category = {known.category}",
            ],
            group_by=["SaleAlias"],
            aggregations=[
                "Sold_Qty = SUM(TotalWeight)",
                "Total_Value = SUM(Value)",
            ],
            calculations=[
                "Avg_Price = SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))",
            ],
            order_by=["SaleAlias"],
            applied_business_rules=self._business_rules(
                analysis,
                ["BR-001 FYear", "BR-002 SaleAlias", "BR-003 AreaAlias", "BR-006 AveragePrice"],
            ),
        )

    def _buyer_purchase_plan(self, analysis: RequirementAnalysis) -> SQLPlan:
        """Build a Buyer Purchase SQL plan."""

        known = analysis.known_information
        season = self._single_season(analysis)
        sale_range = self._sale_range(known.sale_range)
        buyer = self._buyer_name(known.buyer)
        self._require_fields(
            "Buyer Purchase",
            {
                "buyer": buyer,
                "category": known.category,
                "output_grain": known.output_grain,
            },
        )

        return SQLPlan(
            report_type=self.BUYER_PURCHASE_REPORT,
            source_table=self.SOURCE_TABLE,
            filters=[
                f"FYear = {season}",
                self._sale_filter(sale_range),
                f"Category = {known.category}",
                f"BuyerMDM = {buyer}",
            ],
            group_by=["BuyerMDM"],
            aggregations=[
                "Sold_Qty = SUM(TotalWeight)",
                "Total_Value = SUM(Value)",
            ],
            calculations=[
                "Avg_Price = SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))",
            ],
            joins=[
                f"LEFT JOIN {self.BUYER_GROUP_TABLE} ON SaleTransactionView.BuyerMDM = Parcon-BuyerGroup.BuyerMDM",
            ],
            order_by=["Total_Value DESC"],
            applied_business_rules=self._business_rules(
                analysis,
                ["BR-001 FYear", "BR-002 SaleAlias", "BR-015 BuyerGroup"],
            ),
        )

    def _price_band_plan(self, analysis: RequirementAnalysis) -> SQLPlan:
        """Build a Price Band SQL plan."""

        known = analysis.known_information
        season = self._single_season(analysis)
        sale_range = self._sale_range(known.sale_range)
        area_alias = self._sql_area_alias(known.area)
        self._require_fields(
            "Price Band",
            {
                "area": area_alias,
                "category": known.category,
                "output_grain": known.output_grain,
            },
        )

        return SQLPlan(
            report_type=self.PRICE_BAND_REPORT,
            source_table=self.SOURCE_TABLE,
            filters=[
                f"FYear = {season}",
                self._sale_filter(sale_range),
                f"AreaAlias = {area_alias}",
                f"Category = {known.category}",
            ],
            group_by=["GardenMDM", "PriceBand"],
            aggregations=[
                "Sold_Qty = SUM(TotalWeight)",
                "Total_Value = SUM(Value)",
                "Garden_Count = COUNT(DISTINCT GardenMDM)",
            ],
            calculations=[
                "Avg_Price = SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))",
                "PriceBand = CASE on Avg_Price",
                "PriceBandSort = numeric sort order",
            ],
            order_by=["PriceBandSort"],
            applied_business_rules=self._business_rules(
                analysis,
                ["BR-001 FYear", "BR-002 SaleAlias", "BR-003 AreaAlias", "BR-007 PriceBands"],
            ),
        )

    def _comparison_plan(self, analysis: RequirementAnalysis) -> SQLPlan:
        """Build a buyer-wise Comparison SQL plan."""

        known = analysis.known_information
        seasons = list(dict.fromkeys(known.seasons))
        if len(seasons) < 2:
            raise SQLPlanningError("Comparison SQL plan requires two seasons.")
        sale_range = self._sale_range(known.sale_range)
        buyer = self._buyer_name(known.buyer)
        self._require_fields(
            "Comparison",
            {
                "buyer": buyer,
                "category": known.category,
                "output_grain": known.output_grain,
            },
        )

        return SQLPlan(
            report_type=self.COMPARISON_REPORT,
            source_table=self.SOURCE_TABLE,
            filters=[
                f"FYear IN ({', '.join(str(season) for season in seasons[:2])})",
                self._sale_filter(sale_range),
                f"Category = {known.category}",
                f"BuyerMDM = {buyer}",
            ],
            group_by=["FYear", "BuyerMDM"],
            aggregations=[
                "Sold_Qty = SUM(TotalWeight)",
                "Total_Value = SUM(Value)",
            ],
            calculations=[
                "Avg_Price = SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))",
            ],
            joins=[
                f"LEFT JOIN {self.BUYER_GROUP_TABLE} ON SaleTransactionView.BuyerMDM = Parcon-BuyerGroup.BuyerMDM",
            ],
            order_by=["FYear", "BuyerMDM"],
            applied_business_rules=self._business_rules(
                analysis,
                ["BR-001 FYear", "BR-002 SaleAlias", "BR-015 BuyerGroup", "BR-027 HistoricalComparison"],
            ),
        )

    def _single_season(self, analysis: RequirementAnalysis) -> int:
        """Return the single season used by non-comparison reports."""

        known = analysis.known_information
        season = known.season or (known.seasons[0] if known.seasons else None)
        if not season:
            raise SQLPlanningError("SQL plan requires season.")
        return int(season)

    @staticmethod
    def _require_fields(report_name: str, fields: dict[str, object]) -> None:
        """Raise when required fields are missing."""

        missing = [name for name, value in fields.items() if not value]
        if missing:
            raise SQLPlanningError(
                f"Cannot create {report_name} SQL plan. Missing field(s): "
                + ", ".join(missing)
            )

    @staticmethod
    def _sale_range(value: str | None) -> SaleRange:
        """Parse supported sale range text."""

        if not value:
            raise SQLPlanningError("SQL plan requires sale range.")

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

        raise SQLPlanningError("Unsupported sale range format.")

    @staticmethod
    def _sale_filter(sale_range: SaleRange) -> str:
        """Return semantic SaleAlias filter."""

        if sale_range.start == sale_range.end:
            return f"SaleAlias = {sale_range.start}"
        return f"SaleAlias BETWEEN {sale_range.start} AND {sale_range.end}"

    @classmethod
    def _buyer_name(cls, buyer: str | None) -> str | None:
        """Return canonical buyer name from supported aliases."""

        if not buyer:
            return None
        normalized = buyer.strip().upper()
        if normalized in cls.BUYER_MAPPING:
            return cls.BUYER_MAPPING[normalized]
        if normalized in cls.BUYER_MAPPING.values():
            return normalized
        return buyer.strip()

    @staticmethod
    def _sql_area_alias(area: str | None) -> str | None:
        """Return SQL AreaAlias value for grouped areas."""

        if area == "DO":
            return "DO/TR"
        if area == "CA":
            return "CA/TP"
        return area

    @staticmethod
    def _business_rules(
        analysis: RequirementAnalysis,
        defaults: list[str],
    ) -> list[str]:
        """Return applicable business rules from analysis or report defaults."""

        if analysis.business_rules:
            return [
                f"{rule.rule_id} {rule.name}".strip()
                if rule.rule_id
                else rule.name
                for rule in analysis.business_rules
            ]
        return defaults
