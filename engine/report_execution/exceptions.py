"""Typed exceptions for report execution infrastructure."""

from __future__ import annotations


class ReportExecutionError(RuntimeError):
    """Base error for executable report generation failures."""


class BigQueryAuthenticationError(ReportExecutionError):
    """Raised when BigQuery authentication cannot be established."""


class BigQueryExecutionError(ReportExecutionError):
    """Raised when BigQuery cannot execute the query."""


class BigQuerySQLSyntaxError(BigQueryExecutionError):
    """Raised when BigQuery rejects SQL syntax or query semantics."""


class BigQueryPermissionError(BigQueryExecutionError):
    """Raised when BigQuery access is denied."""


class ExcelExportError(ReportExecutionError):
    """Raised when Excel export fails."""


class ExcelFileWriteError(ExcelExportError):
    """Raised when the workbook cannot be written to disk."""

