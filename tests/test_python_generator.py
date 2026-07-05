import inspect

from engine.python_generator.python_generator import PythonGenerator
from engine.python_generator.python_models import PythonGenerationStatus
from engine.requirement_engine.models import (
    DecisionStatus,
    KnownInformation,
    RequirementAnalysis,
)
from engine.sql_engine.sql_generator import SQLGenerator
from engine.sql_planner.sql_planner import SQLPlanner
from engine.sql_review_engine.review_models import SQLReviewResult, SQLReviewStatus
from engine.sql_review_engine.sql_reviewer import SQLReviewer


def _garden_ranking_analysis() -> RequirementAnalysis:
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


def _sale_wise_average_price_analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Sale Wise Average Price Report",
        known_information=KnownInformation(
            report_type="Sale Wise Average Price Report",
            season=2026,
            sale_range="sale 20",
            area="AS",
            category="ORTHODOX",
            metrics=["average price"],
            output_grain="sale-wise",
        ),
        sql_generation_allowed=True,
        decision_status=DecisionStatus.SQL_ALLOWED,
        metadata={"confidence_score": 0.85},
    )


def _buyer_purchase_analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Buyer Purchase Report",
        known_information=KnownInformation(
            report_type="Buyer Purchase Report",
            season=2026,
            sale_range="sale 14 to 26",
            buyer="HUL",
            category="CTC",
            metrics=["quantity", "value"],
            output_grain="buyer-wise",
        ),
        sql_generation_allowed=True,
        decision_status=DecisionStatus.SQL_ALLOWED,
        metadata={"confidence_score": 0.85},
    )


def _price_band_analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Price Band Report",
        known_information=KnownInformation(
            report_type="Price Band Report",
            season=2025,
            sale_range="sale 14 to 26",
            area="DO",
            category="CTC",
            metrics=["price band analysis"],
            output_grain="garden-wise",
        ),
        sql_generation_allowed=True,
        decision_status=DecisionStatus.SQL_ALLOWED,
        metadata={"confidence_score": 0.85},
    )


def _comparison_analysis() -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Comparison Report",
        known_information=KnownInformation(
            report_type="Comparison Report",
            seasons=[2025, 2026],
            sale_range="up to sale 26",
            buyer="TCPL",
            category="CTC",
            metrics=["quantity", "value"],
            output_grain="buyer-wise",
        ),
        sql_generation_allowed=True,
        decision_status=DecisionStatus.SQL_ALLOWED,
        metadata={"confidence_score": 0.85},
    )


def _passed_generation(analysis):
    plan = SQLPlanner().plan(analysis)
    sql_result = SQLGenerator().generate(plan)
    assert sql_result.sql is not None
    review_result = SQLReviewer().review(sql_result.sql, analysis, sql_result)
    assert review_result.status == SQLReviewStatus.PASS
    result = PythonGenerator().generate(
        plan=plan,
        sql=sql_result.sql,
        review_result=review_result,
    )
    return result, sql_result.sql


def test_generates_python_script_for_garden_ranking_report() -> None:
    result, _ = _passed_generation(_garden_ranking_analysis())

    assert result.status == PythonGenerationStatus.GENERATED
    assert result.output_filename == "Garden_Ranking_2026_Upto_Sale_26.xlsx"
    assert "sheet_name=\"Garden Ranking\"" in result.script


def test_generates_python_script_for_sale_wise_average_price_report() -> None:
    result, _ = _passed_generation(_sale_wise_average_price_analysis())

    assert result.status == PythonGenerationStatus.GENERATED
    assert result.output_filename == "Sale_Wise_Average_2026_Sale_20.xlsx"
    assert "sheet_name=\"Sale Wise Average\"" in result.script


def test_generates_python_script_for_buyer_purchase_report() -> None:
    result, _ = _passed_generation(_buyer_purchase_analysis())

    assert result.status == PythonGenerationStatus.GENERATED
    assert result.output_filename == "Buyer_Purchase_HUL_2026_Sale_14_to_26.xlsx"
    assert "sheet_name=\"Buyer Purchase\"" in result.script


def test_generates_python_script_for_price_band_report() -> None:
    result, _ = _passed_generation(_price_band_analysis())

    assert result.status == PythonGenerationStatus.GENERATED
    assert result.output_filename == "Price_Band_DO_TR_2025_Sale_14_to_26.xlsx"
    assert "sheet_name=\"Price Band\"" in result.script


def test_generates_python_script_for_comparison_report() -> None:
    result, _ = _passed_generation(_comparison_analysis())

    assert result.status == PythonGenerationStatus.GENERATED
    assert result.output_filename == "Comparison_TCPL_2025_vs_2026_Upto_Sale_26.xlsx"
    assert "sheet_name=\"Comparison\"" in result.script


def test_blocks_generation_if_sql_review_status_is_fail() -> None:
    plan = SQLPlanner().plan(_garden_ranking_analysis())
    review_result = SQLReviewResult(
        status=SQLReviewStatus.FAIL,
        issues=["Bad SQL"],
        failed_checks=["Example"],
        review_summary="Failed",
        confidence=0.2,
    )

    result = PythonGenerator().generate(
        plan=plan,
        sql="SELECT * FROM table",
        review_result=review_result,
    )

    assert result.status == PythonGenerationStatus.BLOCKED
    assert result.script is None
    assert "SQL review did not pass" in result.reason


def test_generated_script_contains_embedded_sql() -> None:
    result, sql = _passed_generation(_garden_ranking_analysis())

    assert "SQL_QUERY = r\"\"\"" in result.script
    assert sql in result.script


def test_generated_script_contains_bigquery_client_creation() -> None:
    result, _ = _passed_generation(_garden_ranking_analysis())

    assert "from google.cloud import bigquery" in result.script
    assert "client = bigquery.Client()" in result.script


def test_generated_script_contains_dataframe_export_to_excel() -> None:
    result, _ = _passed_generation(_garden_ranking_analysis())

    assert "client.query(SQL_QUERY).to_dataframe()" in result.script
    assert "pd.ExcelWriter" in result.script
    assert "dataframe.to_excel" in result.script


def test_generated_script_contains_openpyxl_formatting_helpers() -> None:
    result, _ = _passed_generation(_garden_ranking_analysis())

    assert "def auto_adjust_column_widths(ws):" in result.script
    assert "def apply_header_style(ws):" in result.script
    assert "def freeze_top_row(ws):" in result.script
    assert "def apply_number_formats(ws):" in result.script


def test_generated_output_filename_is_report_specific() -> None:
    result, _ = _passed_generation(_sale_wise_average_price_analysis())

    assert result.output_filename.startswith("Sale_Wise_Average_")
    assert result.output_filename.endswith(".xlsx")


def test_python_generator_uses_sql_plan_not_requirement_analysis() -> None:
    source = inspect.getsource(PythonGenerator)
    assert "RequirementAnalysis" not in source

    plan = SQLPlanner().plan(_garden_ranking_analysis())
    sql_result = SQLGenerator().generate(plan)
    review_result = SQLReviewer().review(sql_result.sql, _garden_ranking_analysis(), sql_result)

    result = PythonGenerator().generate(
        plan=plan,
        sql=sql_result.sql,
        review_result=review_result,
    )

    assert result.status == PythonGenerationStatus.GENERATED
