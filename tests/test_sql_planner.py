from engine.requirement_engine.models import (
    DecisionStatus,
    KnownInformation,
    RequirementAnalysis,
)
from engine.sql_planner.sql_planner import SQLPlanner, SQLPlanningError


def _analysis(
    *,
    report_type: str,
    decision_status: DecisionStatus | None = DecisionStatus.SQL_ALLOWED,
    season: int | None = None,
    seasons: list[int] | None = None,
    sale_range: str = "sale 14 to 26",
    area: str | None = None,
    category: str | None = "CTC",
    est_blf: str | None = None,
    buyer: str | None = None,
    metrics: list[str] | None = None,
    output_grain: str | None = None,
) -> RequirementAnalysis:
    return RequirementAnalysis(
        summary=report_type,
        known_information=KnownInformation(
            report_type=report_type,
            season=season,
            seasons=seasons or [],
            sale_range=sale_range,
            area=area,
            category=category,
            est_blf=est_blf,
            buyer=buyer,
            metrics=metrics or [],
            output_grain=output_grain,
        ),
        sql_generation_allowed=decision_status == DecisionStatus.SQL_ALLOWED,
        decision_status=decision_status,
        metadata={"confidence_score": 0.85},
    )


def test_garden_ranking_sql_plan() -> None:
    plan = SQLPlanner().plan(
        _analysis(
            report_type="Garden Ranking Report",
            season=2026,
            sale_range="up to sale 26",
            area="AS",
            category="CTC",
            est_blf="EST",
            metrics=["ranking"],
            output_grain="garden-wise",
        )
    )

    assert plan.source_table == "data-warehousing-prod.EasyReports.SaleTransactionView"
    assert "FYear = 2026" in plan.filters
    assert "SaleAlias BETWEEN 14 AND 26" in plan.filters
    assert "AreaAlias = AS" in plan.filters
    assert "Category = CTC" in plan.filters
    assert "EstBlf = EST" in plan.filters
    assert plan.group_by == ["GardenMDM"]
    assert plan.ranking == ["DENSE_RANK over Avg_Price desc"]


def test_sale_wise_average_price_sql_plan() -> None:
    plan = SQLPlanner().plan(
        _analysis(
            report_type="Sale Wise Average Price Report",
            season=2026,
            sale_range="sale 20",
            area="AS",
            category="ORTHODOX",
            metrics=["average price"],
            output_grain="sale-wise",
        )
    )

    assert "FYear = 2026" in plan.filters
    assert "SaleAlias = 20" in plan.filters
    assert "AreaAlias = AS" in plan.filters
    assert "Category = ORTHODOX" in plan.filters
    assert plan.group_by == ["SaleAlias"]
    assert plan.order_by == ["SaleAlias"]


def test_buyer_purchase_sql_plan() -> None:
    plan = SQLPlanner().plan(
        _analysis(
            report_type="Buyer Purchase Report",
            season=2026,
            buyer="HUL",
            category="CTC",
            metrics=["quantity", "value"],
            output_grain="buyer-wise",
        )
    )

    assert "BuyerMDM = HINDUSTHAN UNILEVER LIMITED" in plan.filters
    assert plan.group_by == ["BuyerMDM"]
    assert plan.joins
    assert "Total_Value DESC" in plan.order_by


def test_price_band_sql_plan() -> None:
    plan = SQLPlanner().plan(
        _analysis(
            report_type="Price Band Report",
            season=2025,
            area="DO",
            category="CTC",
            metrics=["price band analysis"],
            output_grain="garden-wise",
        )
    )

    assert "FYear = 2025" in plan.filters
    assert "AreaAlias = DO/TR" in plan.filters
    assert "PriceBand = CASE on Avg_Price" in plan.calculations
    assert "Garden_Count = COUNT(DISTINCT GardenMDM)" in plan.aggregations
    assert "PriceBand" in plan.group_by
    assert plan.order_by == ["PriceBandSort"]


def test_comparison_sql_plan() -> None:
    plan = SQLPlanner().plan(
        _analysis(
            report_type="Comparison Report",
            seasons=[2025, 2026],
            sale_range="up to sale 26",
            buyer="TCPL",
            category="CTC",
            metrics=["quantity", "value"],
            output_grain="buyer-wise",
        )
    )

    assert "FYear IN (2025, 2026)" in plan.filters
    assert "SaleAlias BETWEEN 14 AND 26" in plan.filters
    assert "BuyerMDM = TATA CONSUMER PRODUCTS LTD." in plan.filters
    assert plan.group_by == ["FYear", "BuyerMDM"]
    assert plan.joins


def test_planner_blocks_if_decision_status_is_not_allowed() -> None:
    analysis = _analysis(
        report_type="Garden Ranking Report",
        decision_status=DecisionStatus.SQL_BLOCKED,
        season=2026,
        area="AS",
        est_blf="EST",
        metrics=["ranking"],
        output_grain="garden-wise",
    )

    try:
        SQLPlanner().plan(analysis)
    except SQLPlanningError as exc:
        assert "SQL_ALLOWED" in str(exc)
    else:
        raise AssertionError("Expected SQLPlanningError.")
