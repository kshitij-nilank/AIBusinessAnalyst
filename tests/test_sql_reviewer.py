from engine.requirement_engine.models import (
    DecisionStatus,
    KnownInformation,
    RequirementAnalysis,
)
from engine.sql_engine.sql_generator import SQLGenerator
from engine.sql_engine.sql_models import SQLGenerationResult
from engine.sql_review_engine.review_models import SQLReviewStatus
from engine.sql_review_engine.sql_reviewer import SQLReviewer


def _analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Garden Ranking Report",
        known_information=KnownInformation(
            report_type="Garden Ranking Report",
            season=2026,
            sale_range="up to sale 26",
            area="AS",
            category="CTC",
            est_blf="EST",
            metrics=["ranking"],
            output_grain="garden-wise",
        ),
        sql_generation_allowed=True,
        decision_status=DecisionStatus.SQL_ALLOWED,
        metadata={"confidence_score": 0.85},
    )


def _generated() -> tuple[RequirementAnalysis, SQLGenerationResult, str]:
    analysis = _analysis()
    generation_result = SQLGenerator().generate(analysis)
    assert generation_result.sql is not None
    return analysis, generation_result, generation_result.sql


def test_correct_garden_ranking_sql_passes() -> None:
    analysis, generation_result, sql = _generated()

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.PASS
    assert not result.issues
    assert "FYear derived logic" in result.passed_checks


def test_sql_with_direct_finyear_filter_fails() -> None:
    analysis, generation_result, sql = _generated()
    sql = sql.replace("WHERE FYear = 2026", "WHERE FinYear = 2026")

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.FAIL
    assert "No direct FinYear filter" in result.failed_checks


def test_sql_without_sale_alias_fails() -> None:
    analysis, generation_result, sql = _generated()
    sql = sql.replace("IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo)", "SaleNo")

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.FAIL
    assert "SaleAlias logic" in result.failed_checks


def test_sql_without_area_alias_fails() -> None:
    analysis, generation_result, sql = _generated()
    sql = sql.replace("END AS AreaAlias", "END AS AreaCode")

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.FAIL
    assert "AreaAlias logic" in result.failed_checks


def test_sql_without_safe_divide_fails() -> None:
    analysis, generation_result, sql = _generated()
    sql = sql.replace("SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))", "SUM(Value) / SUM(TotalWeight)")

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.FAIL
    assert "SAFE_DIVIDE average price" in result.failed_checks


def test_sql_without_dense_rank_fails() -> None:
    analysis, generation_result, sql = _generated()
    sql = sql.replace("DENSE_RANK()", "RANK()")

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.FAIL
    assert "DENSE_RANK ranking" in result.failed_checks


def test_sql_with_select_star_fails() -> None:
    analysis, generation_result, sql = _generated()
    sql = sql.replace("SELECT\n        GardenMDM,", "SELECT * FROM (\n    SELECT\n        GardenMDM,")

    result = SQLReviewer().review(sql, analysis, generation_result)

    assert result.status == SQLReviewStatus.FAIL
    assert "No SELECT star" in result.failed_checks
