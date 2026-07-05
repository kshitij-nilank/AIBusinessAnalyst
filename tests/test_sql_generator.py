from engine.requirement_engine.models import (
    DecisionStatus,
    KnownInformation,
    RequirementAnalysis,
)
from engine.sql_engine.sql_generator import SQLGenerationError, SQLGenerator
from engine.sql_engine.sql_models import SQLGenerationStatus


def _garden_ranking_analysis(
    *,
    decision_status: DecisionStatus | None = DecisionStatus.SQL_ALLOWED,
    category: str | None = "CTC",
    sale_range: str = "up to sale 26",
) -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Garden Ranking Report",
        known_information=KnownInformation(
            report_type="Garden Ranking Report",
            season=2026,
            sale_range=sale_range,
            area="AS",
            category=category,
            est_blf="EST",
            metrics=["ranking"],
            output_grain="garden-wise",
        ),
        sql_generation_allowed=decision_status == DecisionStatus.SQL_ALLOWED,
        decision_status=decision_status,
        metadata={"confidence_score": 0.85},
    )


def test_sql_generated_for_complete_garden_ranking_report() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis())

    assert result.status == SQLGenerationStatus.GENERATED
    assert result.report_type == "Garden Ranking Report"
    assert result.sql is not None
    assert "data-warehousing-prod.EasyReports.SaleTransactionView" in result.sql
    assert "GardenMDM" in result.sql
    assert result.source_tables == [
        "data-warehousing-prod.EasyReports.SaleTransactionView"
    ]
    assert result.applied_business_rules


def test_sql_blocked_if_decision_status_is_not_allowed() -> None:
    result = SQLGenerator().generate(
        _garden_ranking_analysis(decision_status=DecisionStatus.SQL_BLOCKED)
    )

    assert result.status == SQLGenerationStatus.BLOCKED
    assert result.sql is None
    assert "decision_status is not SQL_ALLOWED" in result.reason


def test_sql_blocked_if_category_missing() -> None:
    try:
        SQLGenerator().generate(_garden_ranking_analysis(category=None))
    except SQLGenerationError as exc:
        assert "category" in str(exc)
    else:
        raise AssertionError("Expected SQLGenerationError for missing category.")


def test_sql_contains_sale_alias_logic() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis())

    assert "IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo) AS SaleAlias" in result.sql


def test_sql_contains_area_alias_logic() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis())

    assert "WHEN Area = 'AS' THEN 'AS'" in result.sql
    assert "WHEN Area IN ('DO', 'TR') THEN 'DO/TR'" in result.sql
    assert "WHEN Area IN ('CA', 'TP') THEN 'CA/TP'" in result.sql
    assert "ELSE 'OTHERS'" in result.sql


def test_sql_contains_dense_rank() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis())

    assert "DENSE_RANK() OVER (ORDER BY Avg_Price DESC) AS Rank" in result.sql


def test_sql_contains_fyear_derived_logic() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis())

    assert "CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season" in result.sql
    assert "END AS FYear" in result.sql
    assert "WHERE FYear = 2026" in result.sql


def test_sql_does_not_contain_direct_season_filter() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis())

    assert "WHERE Season = 2026" not in result.sql
    assert "AND Season = 2026" not in result.sql


def test_upto_sale_26_becomes_sale_alias_between_14_and_26() -> None:
    result = SQLGenerator().generate(
        _garden_ranking_analysis(sale_range="upto sale 26")
    )

    assert "SaleAlias BETWEEN 14 AND 26" in result.sql


def test_sale_14_to_26_becomes_sale_alias_between_14_and_26() -> None:
    result = SQLGenerator().generate(
        _garden_ranking_analysis(sale_range="sale 14 to 26")
    )

    assert "SaleAlias BETWEEN 14 AND 26" in result.sql


def test_sale_20_becomes_sale_alias_equals_20() -> None:
    result = SQLGenerator().generate(_garden_ranking_analysis(sale_range="sale 20"))

    assert "SaleAlias = 20" in result.sql
    assert "SaleAlias BETWEEN" not in result.sql
