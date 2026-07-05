"""BigQuery execution abstraction."""

from __future__ import annotations

import logging
import time
from typing import Protocol

import pandas as pd

from engine.report_execution.exceptions import (
    BigQueryAuthenticationError,
    BigQueryExecutionError,
    BigQueryPermissionError,
    BigQuerySQLSyntaxError,
)


logger = logging.getLogger(__name__)


class QueryExecutor(Protocol):
    """Protocol for SQL executors that return pandas DataFrames."""

    def execute(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return a DataFrame."""


class BigQueryExecutor:
    """Execute SQL against BigQuery.

    The BigQuery dependency is imported lazily so tests can mock this adapter
    without requiring Google Cloud credentials or network access.
    """

    def __init__(self, *, timeout_seconds: int = 300) -> None:
        """Create a BigQuery executor with a bounded query wait timeout."""

        self.timeout_seconds = timeout_seconds

    def execute(self, sql: str) -> pd.DataFrame:
        """Execute a BigQuery SQL statement and return a pandas DataFrame."""

        started_at = time.perf_counter()
        try:
            client = self._create_client()
            logger.info("Executing SQL...", extra={"event": "bigquery_query_started"})
            query_job = client.query(sql)
            row_iterator = query_job.result(timeout=self.timeout_seconds)
            dataframe = row_iterator.to_dataframe()
        except BigQueryAuthenticationError:
            raise
        except Exception as exc:
            raise self._map_query_error(exc) from exc

        logger.info(
            "Rows returned: %s",
            len(dataframe.index),
            extra={
                "event": "bigquery_query_completed",
                "row_count": len(dataframe.index),
                "execution_time": time.perf_counter() - started_at,
            },
        )
        return dataframe

    @staticmethod
    def _create_client():
        """Authenticate and return a BigQuery client."""

        logger.info("Connecting to BigQuery...", extra={"event": "bigquery_connecting"})
        try:
            from google.auth.exceptions import DefaultCredentialsError, RefreshError
            from google.cloud import bigquery
        except ModuleNotFoundError as exc:
            raise BigQueryAuthenticationError(
                "Google BigQuery dependencies are not installed. Install "
                "google-cloud-bigquery and google-auth to execute reports."
            ) from exc

        try:
            client = bigquery.Client()
        except (DefaultCredentialsError, RefreshError) as exc:
            raise BigQueryAuthenticationError(_credential_guidance(str(exc))) from exc
        except Exception as exc:
            raise BigQueryAuthenticationError(_credential_guidance(str(exc))) from exc

        logger.info(
            "Authentication successful.",
            extra={"event": "bigquery_authentication_successful"},
        )
        return client

    @staticmethod
    def _map_query_error(exc: Exception) -> BigQueryExecutionError:
        """Map Google API exceptions to stable execution-layer errors."""

        try:
            from google.api_core.exceptions import (
                BadRequest,
                DeadlineExceeded,
                Forbidden,
                GoogleAPICallError,
                NotFound,
            )
        except ModuleNotFoundError:
            return BigQueryExecutionError(str(exc))

        if isinstance(exc, BadRequest):
            return BigQuerySQLSyntaxError(f"BigQuery SQL error: {exc}")
        if isinstance(exc, Forbidden):
            return BigQueryPermissionError(f"BigQuery permission denied: {exc}")
        if isinstance(exc, NotFound):
            return BigQueryExecutionError(f"BigQuery resource not found: {exc}")
        if isinstance(exc, DeadlineExceeded) or isinstance(exc, TimeoutError):
            return BigQueryExecutionError(f"BigQuery query timed out: {exc}")
        if isinstance(exc, GoogleAPICallError):
            return BigQueryExecutionError(f"BigQuery API error: {exc}")
        return BigQueryExecutionError(str(exc))


def _credential_guidance(error: str) -> str:
    """Return an actionable BigQuery credential error message."""

    return (
        f"BigQuery authentication failed: {error}\n"
        "Run: gcloud auth application-default login\n"
        "or set: GOOGLE_APPLICATION_CREDENTIALS"
    )
