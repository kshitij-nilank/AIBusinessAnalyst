"""SQL Review Engine v1 for generated BigQuery SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from engine.requirement_engine.models import RequirementAnalysis
from engine.sql_engine.sql_models import SQLGenerationResult
from engine.sql_review_engine.review_models import SQLReviewResult, SQLReviewStatus


@dataclass(frozen=True, slots=True)
class SQLCheck:
    """One deterministic SQL review check."""

    name: str
    predicate: Callable[[str, RequirementAnalysis, SQLGenerationResult], bool]
    failure_message: str
    critical: bool = True


class SQLReviewer:
    """Review generated SQL text without executing it."""

    GARDEN_RANKING_REPORT = "Garden Ranking Report"
    SALE_WISE_AVERAGE_PRICE_REPORT = "Sale Wise Average Price Report"
    BUYER_PURCHASE_REPORT = "Buyer Purchase Report"
    PRICE_BAND_REPORT = "Price Band Report"
    COMPARISON_REPORT = "Comparison Report"

    def review(
        self,
        sql: str,
        analysis: RequirementAnalysis,
        generation_result: SQLGenerationResult,
    ) -> SQLReviewResult:
        """Review generated SQL against business and technical safeguards."""

        if not sql or not sql.strip():
            return SQLReviewResult(
                status=SQLReviewStatus.FAIL,
                issues=["Generated SQL is empty."],
                failed_checks=["SQL is not empty"],
                review_summary="SQL review failed because no SQL text was provided.",
                confidence=0.0,
            )

        checks = self._checks_for_report(generation_result.report_type)
        passed: list[str] = []
        failed: list[str] = []
        issues: list[str] = []
        warnings: list[str] = []

        if not checks:
            return SQLReviewResult(
                status=SQLReviewStatus.WARNING,
                warnings=[
                    "SQL review is not implemented for this report type.",
                ],
                review_summary="SQL review could not apply report-specific checks.",
                confidence=0.0,
            )

        for check in checks:
            if check.predicate(sql, analysis, generation_result):
                passed.append(check.name)
                continue
            failed.append(check.name)
            if check.critical:
                issues.append(check.failure_message)
            else:
                warnings.append(check.failure_message)

        status = self._status(issues, warnings)
        confidence = self._confidence(passed, failed, issues)
        return SQLReviewResult(
            status=status,
            issues=issues,
            warnings=warnings,
            passed_checks=passed,
            failed_checks=failed,
            review_summary=self._summary(status, issues, warnings),
            confidence=confidence,
        )

    def _checks_for_report(self, report_type: str | None) -> tuple[SQLCheck, ...]:
        """Return SQL checks for a supported report type."""

        if report_type == self.GARDEN_RANKING_REPORT:
            return self._garden_ranking_checks()
        if report_type == self.SALE_WISE_AVERAGE_PRICE_REPORT:
            return self._sale_wise_average_price_checks()
        if report_type == self.BUYER_PURCHASE_REPORT:
            return self._buyer_purchase_checks()
        if report_type == self.PRICE_BAND_REPORT:
            return self._price_band_checks()
        if report_type == self.COMPARISON_REPORT:
            return self._comparison_checks()
        return ()

    def _garden_ranking_checks(self) -> tuple[SQLCheck, ...]:
        """Return Garden Ranking SQL checks."""

        return (
            SQLCheck(
                name="FYear derived logic",
                predicate=lambda sql, analysis, result: (
                    "CAST(SUBSTRING(FinYear, 1, 4) AS INT64)" in sql
                ),
                failure_message="FYear derived logic is missing.",
            ),
            SQLCheck(
                name="No direct Season filter",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bWHERE\s+Season\s*=\s*\d+", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL directly filters Season in a WHERE clause.",
            ),
            SQLCheck(
                name="No direct FinYear filter",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bWHERE\s+FinYear\s*=\s*\d+", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL directly filters FinYear instead of derived FYear.",
            ),
            SQLCheck(
                name="SaleAlias logic",
                predicate=lambda sql, analysis, result: (
                    "IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo)" in sql
                ),
                failure_message="SaleAlias logic is missing.",
            ),
            SQLCheck(
                name="AreaAlias logic",
                predicate=self._has_area_alias_logic,
                failure_message="AreaAlias logic is missing.",
            ),
            SQLCheck(
                name="FYear filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bWHERE\s+FYear\s*=", sql, flags=re.IGNORECASE)
                )
                or bool(re.search(r"\bAND\s+FYear\s*=", sql, flags=re.IGNORECASE)),
                failure_message="SQL does not filter using FYear.",
            ),
            SQLCheck(
                name="SaleAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bSaleAlias\s+(BETWEEN|=)", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using SaleAlias.",
            ),
            SQLCheck(
                name="AreaAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bAreaAlias\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using AreaAlias.",
            ),
            SQLCheck(
                name="Category filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bCategory\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using Category.",
            ),
            SQLCheck(
                name="EST/BLF filter",
                predicate=self._has_est_blf_filter,
                failure_message="SQL does not filter using EstBlf.",
            ),
            SQLCheck(
                name="SAFE_DIVIDE average price",
                predicate=lambda sql, analysis, result: "SAFE_DIVIDE" in sql,
                failure_message="Average price does not use SAFE_DIVIDE.",
            ),
            SQLCheck(
                name="DENSE_RANK ranking",
                predicate=lambda sql, analysis, result: "DENSE_RANK" in sql,
                failure_message="Ranking does not use DENSE_RANK.",
            ),
            SQLCheck(
                name="SaleTransactionView source",
                predicate=lambda sql, analysis, result: (
                    "data-warehousing-prod.EasyReports.SaleTransactionView" in sql
                ),
                failure_message="SQL does not use SaleTransactionView.",
            ),
            SQLCheck(
                name="No SELECT star",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bSELECT\s+\*", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL contains SELECT *.",
            ),
            SQLCheck(
                name="GROUP BY GardenMDM",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bGROUP\s+BY\s+GardenMDM\b", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not group by GardenMDM.",
            ),
            SQLCheck(
                name="ORDER BY present",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bORDER\s+BY\b", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL has no ORDER BY clause.",
                critical=False,
            ),
        )

    def _sale_wise_average_price_checks(self) -> tuple[SQLCheck, ...]:
        """Return Sale Wise Average Price SQL checks."""

        return (
            SQLCheck(
                name="FYear derived logic",
                predicate=lambda sql, analysis, result: (
                    "CAST(SUBSTRING(FinYear, 1, 4) AS INT64)" in sql
                ),
                failure_message="FYear derived logic is missing.",
            ),
            SQLCheck(
                name="No direct FinYear filter",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bWHERE\s+FinYear\s*=\s*\d+", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL directly filters FinYear instead of derived FYear.",
            ),
            SQLCheck(
                name="SaleAlias logic",
                predicate=lambda sql, analysis, result: (
                    "IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo)" in sql
                ),
                failure_message="SaleAlias logic is missing.",
            ),
            SQLCheck(
                name="AreaAlias logic",
                predicate=self._has_area_alias_logic,
                failure_message="AreaAlias logic is missing.",
            ),
            SQLCheck(
                name="FYear filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bWHERE\s+FYear\s*=", sql, flags=re.IGNORECASE)
                )
                or bool(re.search(r"\bAND\s+FYear\s*=", sql, flags=re.IGNORECASE)),
                failure_message="SQL does not filter using FYear.",
            ),
            SQLCheck(
                name="SaleAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bSaleAlias\s+(BETWEEN|=)", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using SaleAlias.",
            ),
            SQLCheck(
                name="AreaAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bAreaAlias\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using AreaAlias.",
            ),
            SQLCheck(
                name="Category filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bCategory\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using Category.",
            ),
            SQLCheck(
                name="SAFE_DIVIDE average price",
                predicate=lambda sql, analysis, result: "SAFE_DIVIDE" in sql,
                failure_message="Average price does not use SAFE_DIVIDE.",
            ),
            SQLCheck(
                name="SaleTransactionView source",
                predicate=lambda sql, analysis, result: (
                    "data-warehousing-prod.EasyReports.SaleTransactionView" in sql
                ),
                failure_message="SQL does not use SaleTransactionView.",
            ),
            SQLCheck(
                name="No SELECT star",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bSELECT\s+\*", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL contains SELECT *.",
            ),
            SQLCheck(
                name="GROUP BY SaleAlias",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bGROUP\s+BY\s+SaleAlias\b", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not group by SaleAlias.",
            ),
            SQLCheck(
                name="ORDER BY SaleAlias",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bORDER\s+BY\s+SaleAlias\b", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not order by SaleAlias.",
            ),
        )

    def _buyer_purchase_checks(self) -> tuple[SQLCheck, ...]:
        """Return Buyer Purchase SQL checks."""

        return (
            SQLCheck(
                name="FYear derived logic",
                predicate=lambda sql, analysis, result: (
                    "CAST(SUBSTRING(sales.FinYear, 1, 4) AS INT64)" in sql
                    or "CAST(SUBSTRING(FinYear, 1, 4) AS INT64)" in sql
                ),
                failure_message="FYear derived logic is missing.",
            ),
            SQLCheck(
                name="No direct FinYear filter",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bWHERE\s+(?:sales\.)?FinYear\s*=\s*\d+",
                    sql,
                    flags=re.IGNORECASE,
                ),
                failure_message="SQL directly filters FinYear instead of derived FYear.",
            ),
            SQLCheck(
                name="SaleAlias logic",
                predicate=lambda sql, analysis, result: (
                    "IF(sales.SaleNo BETWEEN 1 AND 13, 53 + sales.SaleNo, sales.SaleNo)"
                    in sql
                )
                or ("IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo)" in sql),
                failure_message="SaleAlias logic is missing.",
            ),
            SQLCheck(
                name="FYear filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bWHERE\s+FYear\s*=", sql, flags=re.IGNORECASE)
                )
                or bool(re.search(r"\bAND\s+FYear\s*=", sql, flags=re.IGNORECASE)),
                failure_message="SQL does not filter using FYear.",
            ),
            SQLCheck(
                name="SaleAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bSaleAlias\s+(BETWEEN|=)", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using SaleAlias.",
            ),
            SQLCheck(
                name="Category filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bCategory\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using Category.",
            ),
            SQLCheck(
                name="BuyerMDM mapping",
                predicate=lambda sql, analysis, result: (
                    "data-warehousing-prod.EasyReports.Parcon-BuyerGroup" in sql
                    and "BuyerMDM" in sql
                ),
                failure_message="SQL does not use Parcon-BuyerGroup BuyerMDM mapping.",
            ),
            SQLCheck(
                name="Sold_Qty aggregate",
                predicate=lambda sql, analysis, result: (
                    "SUM(TotalWeight) AS Sold_Qty" in sql
                ),
                failure_message="SQL does not calculate Sold_Qty.",
            ),
            SQLCheck(
                name="Total_Value aggregate",
                predicate=lambda sql, analysis, result: "SUM(Value) AS Total_Value" in sql,
                failure_message="SQL does not calculate Total_Value.",
            ),
            SQLCheck(
                name="SAFE_DIVIDE average price",
                predicate=lambda sql, analysis, result: "SAFE_DIVIDE" in sql,
                failure_message="Average price does not use SAFE_DIVIDE.",
            ),
            SQLCheck(
                name="Buyer-wise GROUP BY",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bGROUP\s+BY\s+BuyerMDM\b", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not group buyer-wise.",
            ),
            SQLCheck(
                name="SaleTransactionView source",
                predicate=lambda sql, analysis, result: (
                    "data-warehousing-prod.EasyReports.SaleTransactionView" in sql
                ),
                failure_message="SQL does not use SaleTransactionView.",
            ),
            SQLCheck(
                name="No SELECT star",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bSELECT\s+\*", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL contains SELECT *.",
            ),
        )

    def _price_band_checks(self) -> tuple[SQLCheck, ...]:
        """Return Price Band SQL checks."""

        return (
            SQLCheck(
                name="FYear derived logic",
                predicate=lambda sql, analysis, result: (
                    "CAST(SUBSTRING(FinYear, 1, 4) AS INT64)" in sql
                ),
                failure_message="FYear derived logic is missing.",
            ),
            SQLCheck(
                name="SaleAlias logic",
                predicate=lambda sql, analysis, result: (
                    "IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo)" in sql
                ),
                failure_message="SaleAlias logic is missing.",
            ),
            SQLCheck(
                name="AreaAlias logic",
                predicate=self._has_area_alias_logic,
                failure_message="AreaAlias logic is missing.",
            ),
            SQLCheck(
                name="FYear filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bWHERE\s+FYear\s*=", sql, flags=re.IGNORECASE)
                )
                or bool(re.search(r"\bAND\s+FYear\s*=", sql, flags=re.IGNORECASE)),
                failure_message="SQL does not filter using FYear.",
            ),
            SQLCheck(
                name="SaleAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bSaleAlias\s+(BETWEEN|=)", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using SaleAlias.",
            ),
            SQLCheck(
                name="AreaAlias filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bAreaAlias\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using AreaAlias.",
            ),
            SQLCheck(
                name="Category filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bCategory\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using Category.",
            ),
            SQLCheck(
                name="PriceBand CASE",
                predicate=lambda sql, analysis, result: (
                    "CASE" in sql and "END AS PriceBand" in sql
                ),
                failure_message="SQL does not create PriceBand using CASE.",
            ),
            SQLCheck(
                name="SAFE_DIVIDE average price",
                predicate=lambda sql, analysis, result: "SAFE_DIVIDE" in sql,
                failure_message="Average price does not use SAFE_DIVIDE.",
            ),
            SQLCheck(
                name="GROUP BY PriceBand",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bGROUP\s+BY\s+PriceBand\b", sql, flags=re.IGNORECASE)
                )
                or bool(
                    re.search(
                        r"\bGROUP\s+BY\s+PriceBand\s*,\s*PriceBandSort\b",
                        sql,
                        flags=re.IGNORECASE,
                    )
                ),
                failure_message="SQL does not group final output by PriceBand.",
            ),
            SQLCheck(
                name="SaleTransactionView source",
                predicate=lambda sql, analysis, result: (
                    "data-warehousing-prod.EasyReports.SaleTransactionView" in sql
                ),
                failure_message="SQL does not use SaleTransactionView.",
            ),
            SQLCheck(
                name="No SELECT star",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bSELECT\s+\*", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL contains SELECT *.",
            ),
        )

    def _comparison_checks(self) -> tuple[SQLCheck, ...]:
        """Return Comparison Report SQL checks."""

        return (
            SQLCheck(
                name="FYear derived logic",
                predicate=lambda sql, analysis, result: (
                    "CAST(SUBSTRING(sales.FinYear, 1, 4) AS INT64)" in sql
                    or "CAST(SUBSTRING(FinYear, 1, 4) AS INT64)" in sql
                ),
                failure_message="FYear derived logic is missing.",
            ),
            SQLCheck(
                name="SaleAlias logic",
                predicate=lambda sql, analysis, result: (
                    "IF(sales.SaleNo BETWEEN 1 AND 13, 53 + sales.SaleNo, sales.SaleNo)"
                    in sql
                )
                or ("IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo)" in sql),
                failure_message="SaleAlias logic is missing.",
            ),
            SQLCheck(
                name="FYear IN comparison seasons",
                predicate=self._has_comparison_seasons,
                failure_message="SQL does not filter FYear IN with both comparison seasons.",
            ),
            SQLCheck(
                name="Category filter",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bCategory\s*=", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not filter using Category.",
            ),
            SQLCheck(
                name="Buyer mapping filter",
                predicate=lambda sql, analysis, result: (
                    "data-warehousing-prod.EasyReports.Parcon-BuyerGroup" in sql
                    and "BuyerMDM" in sql
                    and re.search(r"\bBuyerMDM\s*=", sql, flags=re.IGNORECASE)
                    is not None
                ),
                failure_message="SQL does not use buyer mapping/filter.",
            ),
            SQLCheck(
                name="GROUP BY FYear",
                predicate=lambda sql, analysis, result: bool(
                    re.search(r"\bGROUP\s+BY\s+FYear\b", sql, flags=re.IGNORECASE)
                ),
                failure_message="SQL does not group by FYear.",
            ),
            SQLCheck(
                name="SAFE_DIVIDE average price",
                predicate=lambda sql, analysis, result: "SAFE_DIVIDE" in sql,
                failure_message="Average price does not use SAFE_DIVIDE.",
            ),
            SQLCheck(
                name="No SELECT star",
                predicate=lambda sql, analysis, result: not re.search(
                    r"\bSELECT\s+\*", sql, flags=re.IGNORECASE
                ),
                failure_message="SQL contains SELECT *.",
            ),
        )

    @staticmethod
    def _has_area_alias_logic(
        sql: str,
        analysis: RequirementAnalysis,
        result: SQLGenerationResult,
    ) -> bool:
        """Return whether expected AreaAlias CASE logic is present."""

        return all(
            fragment in sql
            for fragment in (
                "WHEN Area = 'AS' THEN 'AS'",
                "WHEN Area IN ('DO', 'TR') THEN 'DO/TR'",
                "WHEN Area IN ('CA', 'TP') THEN 'CA/TP'",
                "ELSE 'OTHERS'",
                "END AS AreaAlias",
            )
        )

    @staticmethod
    def _has_est_blf_filter(
        sql: str,
        analysis: RequirementAnalysis,
        result: SQLGenerationResult,
    ) -> bool:
        """Require EstBlf filter only when EST/BLF is present in the analysis."""

        if not analysis.known_information.est_blf:
            return True
        return bool(re.search(r"\bEstBlf\s*=", sql, flags=re.IGNORECASE))

    @staticmethod
    def _has_comparison_seasons(
        sql: str,
        analysis: RequirementAnalysis,
        result: SQLGenerationResult,
    ) -> bool:
        """Return whether SQL filters FYear IN with both comparison seasons."""

        seasons = [str(season) for season in analysis.known_information.seasons[:2]]
        if len(seasons) < 2:
            return False
        compact_sql = re.sub(r"\s+", " ", sql)
        match = re.search(r"\bFYear\s+IN\s*\(([^)]*)\)", compact_sql, re.IGNORECASE)
        if not match:
            return False
        selected = {value.strip() for value in match.group(1).split(",")}
        return set(seasons).issubset(selected)

    @staticmethod
    def _status(issues: list[str], warnings: list[str]) -> SQLReviewStatus:
        """Return overall review status."""

        if issues:
            return SQLReviewStatus.FAIL
        if warnings:
            return SQLReviewStatus.WARNING
        return SQLReviewStatus.PASS

    @staticmethod
    def _confidence(
        passed_checks: list[str],
        failed_checks: list[str],
        issues: list[str],
    ) -> float:
        """Calculate a simple review confidence score."""

        total = len(passed_checks) + len(failed_checks)
        if total == 0:
            return 0.0
        base = len(passed_checks) / total
        if issues:
            base = min(base, 0.65)
        return round(max(0.0, min(1.0, base)), 4)

    @staticmethod
    def _summary(
        status: SQLReviewStatus,
        issues: list[str],
        warnings: list[str],
    ) -> str:
        """Return human-readable review summary."""

        if status == SQLReviewStatus.PASS:
            return "SQL review passed all critical report checks."
        if status == SQLReviewStatus.WARNING:
            return "SQL review passed critical checks with warnings."
        return f"SQL review failed with {len(issues)} critical issue(s)."
