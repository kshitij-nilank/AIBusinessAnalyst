"""Report execution engine."""

from __future__ import annotations

import logging
import time

from engine.report_execution.bigquery_executor import BigQueryExecutor, QueryExecutor
from engine.report_execution.exceptions import (
    BigQueryAuthenticationError,
    BigQueryExecutionError,
    ExcelExportError,
    ExcelFileWriteError,
    ReportExecutionError,
)
from engine.report_execution.excel_exporter import DataFrameExporter, ExcelExporter
from engine.report_execution.filename_builder import ReportFilenameBuilder
from engine.report_execution.models import (
    ReportExecutionResult,
    ReportExecutionStatus,
)
from engine.sql_planner.plan_models import SQLPlan
from engine.sql_review_engine.review_models import SQLReviewResult, SQLReviewStatus


logger = logging.getLogger(__name__)


class ReportExecutionEngine:
    """Execute reviewed SQL and export the result to Excel."""

    def __init__(
        self,
        *,
        query_executor: QueryExecutor | None = None,
        exporter: DataFrameExporter | None = None,
        filename_builder: ReportFilenameBuilder | None = None,
    ) -> None:
        """Create an execution engine with injectable infrastructure."""

        self.query_executor = query_executor or BigQueryExecutor()
        self.exporter = exporter or ExcelExporter()
        self.filename_builder = filename_builder or ReportFilenameBuilder()

    def execute(
        self,
        *,
        plan: SQLPlan,
        sql: str,
        review_result: SQLReviewResult,
    ) -> ReportExecutionResult:
        """Execute reviewed SQL and export the resulting DataFrame to Excel."""

        if review_result.status != SQLReviewStatus.PASS:
            logger.info(
                "Report execution blocked because SQL review did not pass.",
                extra={"event": "report_execution_blocked"},
            )
            return ReportExecutionResult(
                status=ReportExecutionStatus.BLOCKED,
                warnings=list(review_result.warnings),
                error_message="Report execution blocked because SQL review did not pass.",
            )

        started_at = time.perf_counter()
        row_count: int | None = None
        try:
            logger.info(
                "Executing Report...",
                extra={"event": "report_execution_started", "report_type": plan.report_type},
            )
            logger.info("BigQuery Authentication...", extra={"event": "report_auth_stage"})
            dataframe = self.query_executor.execute(sql)
            logger.info("Creating DataFrame...", extra={"event": "report_dataframe_created"})
            row_count = len(dataframe.index)
            logger.info(
                "Rows Returned: %s",
                row_count,
                extra={"event": "report_rows_returned", "row_count": row_count},
            )
            output_filename = self.filename_builder.build(plan)
            logger.info(
                "Exporting Excel...",
                extra={"event": "report_excel_export_started", "output_filename": output_filename},
            )
            output_file = self.exporter.export(dataframe, output_filename)
        except BigQueryAuthenticationError as exc:
            return self._failed_result(exc, started_at, row_count, review_result)
        except BigQueryExecutionError as exc:
            return self._failed_result(exc, started_at, row_count, review_result)
        except ExcelFileWriteError as exc:
            return self._failed_result(exc, started_at, row_count, review_result)
        except ExcelExportError as exc:
            return self._failed_result(exc, started_at, row_count, review_result)
        except ReportExecutionError as exc:
            return self._failed_result(exc, started_at, row_count, review_result)
        except PermissionError as exc:
            return self._failed_result(
                ExcelFileWriteError(f"File write permission error: {exc}"),
                started_at,
                row_count,
                review_result,
            )
        except Exception as exc:
            return self._failed_result(
                ReportExecutionError(str(exc)),
                started_at,
                row_count,
                review_result,
            )

        execution_time = time.perf_counter() - started_at
        logger.info(
            "Execution Completed.",
            extra={
                "event": "report_execution_completed",
                "output_file": output_file,
                "row_count": row_count,
                "execution_time": execution_time,
            },
        )
        return ReportExecutionResult(
            status=ReportExecutionStatus.SUCCESS,
            output_file=output_file,
            row_count=row_count,
            execution_time=execution_time,
            warnings=list(review_result.warnings),
        )

    @staticmethod
    def _failed_result(
        exc: Exception,
        started_at: float,
        row_count: int | None,
        review_result: SQLReviewResult,
    ) -> ReportExecutionResult:
        """Build a failed execution result and log the full error."""

        execution_time = time.perf_counter() - started_at
        logger.info(
            "Execution Failed. Reason: %s",
            exc,
            extra={
                "event": "report_execution_failed",
                "row_count": row_count,
                "execution_time": execution_time,
            },
        )
        return ReportExecutionResult(
            status=ReportExecutionStatus.FAILED,
            row_count=row_count,
            execution_time=execution_time,
            warnings=list(review_result.warnings),
            error_message=str(exc),
        )
