import re
from tempfile import TemporaryDirectory

import pandas as pd

from engine.report_execution.exceptions import (
    BigQueryAuthenticationError,
    BigQueryExecutionError,
)
from engine.report_execution.excel_exporter import ExcelExporter
from engine.report_execution.models import ReportExecutionStatus
from engine.report_execution.report_execution_engine import ReportExecutionEngine
from engine.sql_planner.plan_models import SQLPlan
from engine.sql_review_engine.review_models import SQLReviewResult, SQLReviewStatus


class FakeBigQueryExecutor:
    def __init__(self, dataframe: pd.DataFrame | None = None, error: Exception | None = None):
        self.dataframe = dataframe if dataframe is not None else pd.DataFrame()
        self.error = error
        self.executed_sql: str | None = None

    def execute(self, sql: str) -> pd.DataFrame:
        self.executed_sql = sql
        if self.error:
            raise self.error
        return self.dataframe


class FakeExcelExporter:
    def __init__(self, output_file: str = "report.xlsx", error: Exception | None = None):
        self.output_file = output_file
        self.error = error
        self.received_dataframe: pd.DataFrame | None = None
        self.received_filename: str | None = None

    def export(self, dataframe: pd.DataFrame, output_filename: str) -> str:
        self.received_dataframe = dataframe
        self.received_filename = output_filename
        if self.error:
            raise self.error
        return self.output_file


def _plan() -> SQLPlan:
    return SQLPlan(
        report_type="Garden Ranking Report",
        source_table="data-warehousing-prod.EasyReports.SaleTransactionView",
        filters=[
            "FYear = 2026",
            "SaleAlias BETWEEN 14 AND 26",
            "AreaAlias = AS",
            "Category = CTC",
            "EstBlf = EST",
        ],
        group_by=["GardenMDM"],
        aggregations=["Sold_Qty = SUM(TotalWeight)"],
        calculations=["Avg_Price = SAFE_DIVIDE(SUM(Value), SUM(TotalWeight))"],
        ranking=["DENSE_RANK over Avg_Price desc"],
        order_by=["Rank", "GardenMDM"],
        applied_business_rules=["BR-001 FYear"],
    )


def _pass_review() -> SQLReviewResult:
    return SQLReviewResult(
        status=SQLReviewStatus.PASS,
        review_summary="SQL passed.",
        confidence=0.95,
    )


def _fail_review() -> SQLReviewResult:
    return SQLReviewResult(
        status=SQLReviewStatus.FAIL,
        issues=["Invalid SQL"],
        failed_checks=["FYear logic"],
        review_summary="SQL failed.",
        confidence=0.2,
    )


def test_successful_execution() -> None:
    executor = FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A", "B"]}))
    exporter = FakeExcelExporter("Garden_Ranking_2026_Upto_Sale_26.xlsx")
    engine = ReportExecutionEngine(query_executor=executor, exporter=exporter)

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.status == ReportExecutionStatus.SUCCESS
    assert result.output_file == "Garden_Ranking_2026_Upto_Sale_26.xlsx"


def test_review_failure_blocks_execution() -> None:
    executor = FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A"]}))
    exporter = FakeExcelExporter()
    engine = ReportExecutionEngine(query_executor=executor, exporter=exporter)

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_fail_review())

    assert result.status == ReportExecutionStatus.BLOCKED
    assert executor.executed_sql is None
    assert exporter.received_dataframe is None


def test_dataframe_passed_to_exporter() -> None:
    dataframe = pd.DataFrame({"GardenMDM": ["A"], "Sold_Qty": [100]})
    exporter = FakeExcelExporter()
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(dataframe),
        exporter=exporter,
    )

    engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert exporter.received_dataframe is dataframe


def test_output_filename_returned() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A"]})),
        exporter=FakeExcelExporter("output/report.xlsx"),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.output_file == "output/report.xlsx"


def test_execution_time_populated() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A"]})),
        exporter=FakeExcelExporter(),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.execution_time is not None
    assert result.execution_time >= 0.0


def test_row_count_populated() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A", "B", "C"]})),
        exporter=FakeExcelExporter(),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.row_count == 3


def test_bigquery_exception_handled() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(error=BigQueryExecutionError("BigQuery failed")),
        exporter=FakeExcelExporter(),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.status == ReportExecutionStatus.FAILED
    assert result.error_message == "BigQuery failed"


def test_authentication_failure_handled() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(
            error=BigQueryAuthenticationError(
                "BigQuery authentication failed. Run: gcloud auth application-default login"
            )
        ),
        exporter=FakeExcelExporter(),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.status == ReportExecutionStatus.FAILED
    assert "authentication failed" in result.error_message


def test_query_execution_failure_handled() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(error=BigQueryExecutionError("Query failed")),
        exporter=FakeExcelExporter(),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.status == ReportExecutionStatus.FAILED
    assert result.error_message == "Query failed"


def test_excel_export_exception_handled() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A"]})),
        exporter=FakeExcelExporter(error=RuntimeError("Excel failed")),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.status == ReportExecutionStatus.FAILED
    assert result.row_count == 1
    assert result.error_message == "Excel failed"


def test_report_execution_result_returned() -> None:
    engine = ReportExecutionEngine(
        query_executor=FakeBigQueryExecutor(pd.DataFrame({"GardenMDM": ["A"]})),
        exporter=FakeExcelExporter(),
    )

    result = engine.execute(plan=_plan(), sql="SELECT 1", review_result=_pass_review())

    assert result.status in {
        ReportExecutionStatus.SUCCESS,
        ReportExecutionStatus.FAILED,
        ReportExecutionStatus.BLOCKED,
    }


def test_output_folder_auto_created_without_excel_write() -> None:
    with TemporaryDirectory() as temp_dir:
        exporter = ExcelExporter(output_dir=f"{temp_dir}/reports/output")
        output_path = exporter.prepare_output_path("Garden_Ranking_2026.xlsx")

        assert exporter.output_dir.exists()
        assert output_path.name == "Garden_Ranking_2026.xlsx"


def test_timestamp_naming_without_overwrite() -> None:
    with TemporaryDirectory() as temp_dir:
        exporter = ExcelExporter(output_dir=temp_dir)
        existing_path = exporter.output_dir / "Garden_Ranking_2026.xlsx"
        existing_path.touch()

        output_path = exporter.prepare_output_path("Garden_Ranking_2026.xlsx")

        assert output_path != existing_path
        assert re.match(
            r"Garden_Ranking_2026_\d{8}_\d{6}\.xlsx",
            output_path.name,
        )


def test_excel_exporter_prepares_absolute_output_path_without_excel_write() -> None:
    with TemporaryDirectory() as temp_dir:
        exporter = ExcelExporter(output_dir=temp_dir)
        output_path = exporter.prepare_output_path("Garden_Ranking_2026.xlsx")

        assert output_path.name == "Garden_Ranking_2026.xlsx"
        assert output_path.is_absolute()
