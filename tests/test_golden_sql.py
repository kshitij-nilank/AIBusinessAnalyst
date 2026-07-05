import re
from pathlib import Path

from engine.requirement_engine.models import (
    DecisionStatus,
    KnownInformation,
    RequirementAnalysis,
)
from engine.sql_engine.sql_generator import SQLGenerator
from engine.sql_planner.sql_planner import SQLPlanner


GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _analysis(report_type: str, **known_fields: object) -> RequirementAnalysis:
    return RequirementAnalysis(
        summary=report_type,
        known_information=KnownInformation(
            report_type=report_type,
            **known_fields,
        ),
        sql_generation_allowed=True,
        decision_status=DecisionStatus.SQL_ALLOWED,
        metadata={"confidence_score": 0.85},
    )


def _render(report_type: str, **known_fields: object) -> str:
    plan = SQLPlanner().plan(_analysis(report_type, **known_fields))
    result = SQLGenerator().generate(plan)
    assert result.sql is not None
    return result.sql


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _assert_matches_golden(filename: str, sql: str) -> None:
    expected = (GOLDEN_DIR / filename).read_text(encoding="utf-8")
    assert _normalize(sql) == _normalize(expected)


def test_garden_ranking_matches_golden_sql() -> None:
    sql = _render(
        "Garden Ranking Report",
        season=2026,
        sale_range="up to sale 26",
        area="AS",
        category="CTC",
        est_blf="EST",
        metrics=["ranking"],
        output_grain="garden-wise",
    )

    _assert_matches_golden("garden_ranking.sql", sql)


def test_sale_wise_average_matches_golden_sql() -> None:
    sql = _render(
        "Sale Wise Average Price Report",
        season=2026,
        sale_range="sale 20",
        area="AS",
        category="ORTHODOX",
        metrics=["average price"],
        output_grain="sale-wise",
    )

    _assert_matches_golden("sale_wise_average.sql", sql)


def test_buyer_purchase_matches_golden_sql() -> None:
    sql = _render(
        "Buyer Purchase Report",
        season=2026,
        sale_range="sale 14 to 26",
        buyer="HUL",
        category="CTC",
        metrics=["quantity", "value"],
        output_grain="buyer-wise",
    )

    _assert_matches_golden("buyer_purchase.sql", sql)


def test_price_band_matches_golden_sql() -> None:
    sql = _render(
        "Price Band Report",
        season=2025,
        sale_range="sale 14 to 26",
        area="DO",
        category="CTC",
        metrics=["price band analysis"],
        output_grain="garden-wise",
    )

    _assert_matches_golden("price_band.sql", sql)


def test_comparison_matches_golden_sql() -> None:
    sql = _render(
        "Comparison Report",
        seasons=[2025, 2026],
        sale_range="up to sale 26",
        buyer="TCPL",
        category="CTC",
        metrics=["quantity", "value"],
        output_grain="buyer-wise",
    )

    _assert_matches_golden("comparison.sql", sql)


def test_expected_templates_are_selected() -> None:
    generator = SQLGenerator()

    assert generator.get_template_name("Garden Ranking Report") == "garden_ranking.sql.j2"
    assert (
        generator.get_template_name("Sale Wise Average Price Report")
        == "sale_wise_average.sql.j2"
    )
    assert generator.get_template_name("Buyer Purchase Report") == "buyer_purchase.sql.j2"
    assert generator.get_template_name("Price Band Report") == "price_band.sql.j2"
    assert generator.get_template_name("Comparison Report") == "comparison.sql.j2"
