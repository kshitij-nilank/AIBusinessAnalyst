"""Lightweight project test runner.

This runner executes test functions directly so the project can be checked
without requiring pytest to be installed.
"""

from __future__ import annotations

import runpy
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from engine.common.llm_client import OfflineRequirementLLMClient
from engine.requirement_engine.knowledge_loader import KnowledgeLoader
from engine.requirement_engine.models import DecisionStatus
from engine.requirement_engine.orchestrator import RequirementUnderstandingOrchestrator
from engine.requirement_engine.prompt_builder import PromptBuilder
from engine.requirement_engine.response_parser import RequirementResponseParser
from engine.requirement_engine.validator import RequirementValidator
from engine.sql_engine.sql_generator import SQLGenerator
from engine.sql_engine.sql_models import SQLGenerationStatus
from engine.sql_review_engine.review_models import SQLReviewStatus
from engine.sql_review_engine.sql_reviewer import SQLReviewer


TEST_DIR = Path(__file__).resolve().parent / "tests"


@dataclass(frozen=True, slots=True)
class ReportFlowCase:
    """One supported report flow smoke test."""

    name: str
    requirement: str
    expected_report_type: str


REPORT_FLOW_CASES = (
    ReportFlowCase(
        name="Garden Ranking Report",
        requirement="garden ranking for assam ctc est season 2026 upto sale 26",
        expected_report_type="Garden Ranking Report",
    ),
    ReportFlowCase(
        name="Sale Wise Average Price Report",
        requirement="sale wise average price for assam orthodox season 2026 sale 20",
        expected_report_type="Sale Wise Average Price Report",
    ),
    ReportFlowCase(
        name="Buyer Purchase Report",
        requirement="buyer wise purchase report for HUL ctc season 2026 sale 14 to 26",
        expected_report_type="Buyer Purchase Report",
    ),
    ReportFlowCase(
        name="Price Band Report",
        requirement="garden wise price band report for dooars ctc season 2025 sale 14 to 26",
        expected_report_type="Price Band Report",
    ),
    ReportFlowCase(
        name="Comparison Report",
        requirement="compare TCPL buying 2025 vs 2026 upto sale 26 ctc buyer wise",
        expected_report_type="Comparison Report",
    ),
)


def main() -> int:
    """Run all test functions under the tests directory."""

    if not TEST_DIR.exists():
        print(f"Test directory not found: {TEST_DIR}")
        return 1

    test_files = sorted(TEST_DIR.glob("test_*.py"))
    if not test_files:
        print("No test files found.")
        return 1

    total = 0
    failed = 0

    for test_file in test_files:
        namespace = runpy.run_path(str(test_file))
        test_functions = _find_test_functions(namespace)

        for name, test_function in test_functions:
            total += 1
            label = f"{test_file.name}::{name}"
            try:
                test_function()
            except Exception:
                failed += 1
                print(f"FAIL {label}")
                traceback.print_exc()
            else:
                print(f"PASS {label}")

    flow_total, flow_failed = _run_report_flow_tests()
    total += flow_total
    failed += flow_failed

    print()
    print(f"Tests run: {total}")
    print(f"Passed: {total - failed}")
    print(f"Failed: {failed}")

    return 1 if failed else 0


def _run_report_flow_tests() -> tuple[int, int]:
    """Run end-to-end smoke tests for supported report flows."""

    orchestrator = RequirementUnderstandingOrchestrator(
        knowledge_loader=KnowledgeLoader(),
        prompt_builder=PromptBuilder(),
        llm_client=OfflineRequirementLLMClient(),
        response_parser=RequirementResponseParser(),
        requirement_validator=RequirementValidator(),
    )
    sql_generator = SQLGenerator()
    sql_reviewer = SQLReviewer()

    total = 0
    failed = 0

    print()
    print("Report flow tests")
    print("-----------------")

    for case in REPORT_FLOW_CASES:
        total += 1
        label = f"report_flow::{case.name}"
        try:
            analysis = orchestrator.analyze(case.requirement)
            assert analysis.known_information.report_type == case.expected_report_type
            assert analysis.decision_status == DecisionStatus.SQL_ALLOWED

            generation_result = sql_generator.generate(analysis)
            assert generation_result.status == SQLGenerationStatus.GENERATED
            assert generation_result.sql

            review_result = sql_reviewer.review(
                generation_result.sql,
                analysis,
                generation_result,
            )
            assert review_result.status == SQLReviewStatus.PASS
        except Exception:
            failed += 1
            print(f"FAIL {label}")
            traceback.print_exc()
        else:
            print(f"PASS {label}")

    return total, failed


def _find_test_functions(
    namespace: dict[str, object],
) -> list[tuple[str, Callable[[], object]]]:
    """Return test functions from a runpy namespace."""

    tests: list[tuple[str, Callable[[], object]]] = []
    for name, value in namespace.items():
        if name.startswith("test_") and callable(value):
            tests.append((name, value))
    return sorted(tests, key=lambda item: item[0])


if __name__ == "__main__":
    raise SystemExit(main())
