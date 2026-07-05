import json
import os

import main
from engine.common.llm_client import OfflineRequirementLLMClient
from engine.requirement_engine.knowledge_loader import KnowledgeLoader
from engine.requirement_engine.orchestrator import RequirementUnderstandingOrchestrator
from engine.requirement_engine.prompt_builder import PromptBuilder
from engine.requirement_engine.response_parser import RequirementResponseParser
from engine.requirement_engine.validator import RequirementValidator


def test_main_orchestrator_offline_fallback_blocks_incomplete_requirement() -> None:
    saved_env = {
        key: os.environ.pop(key, None)
        for key in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_PROVIDER")
    }
    try:
        orchestrator = main.build_orchestrator()
        result = orchestrator.analyze("Need Garden Report")
    finally:
        for key, value in saved_env.items():
            if value is not None:
                os.environ[key] = value

    assert result.sql_generation_allowed is False
    assert result.clarification_questions
    assert "season_or_financial_year" in result.metadata["missing_mandatory_fields"]


def test_response_parser_prefers_outer_json_before_markdown_fences() -> None:
    payload = json.dumps(
        {
            "summary": "Requirement received",
            "known_information": {
                "raw_request_text": "Prompt contains ```sql\nSELECT 1\n``` text.",
            },
        }
    )

    result = RequirementResponseParser().parse(payload)

    assert result.ok is True
    assert result.analysis is not None
    assert result.analysis.summary == "Requirement received"


def test_hookmol_requirement_response_maps_to_known_information() -> None:
    raw_llm_response = json.dumps(
        {
            "summary": "Garden average comparison report.",
            "knownInformation": {
                "reportType": "Garden Average Report",
                "gardenName": "HOOKMOL",
                "season": "2025 vs 2026",
                "saleRange": "up to Sale 26",
                "metric": "average price",
                "groupingLevel": "garden-wise",
                "rawRequirement": (
                    "GIVE HOOKMOL GARDEN AVERAGES FOR SEASON 2025 VS 2026 "
                    "UPTO SALE 26"
                ),
            },
            "metadata": {"confidence_score": 0.9},
        }
    )

    parsed = RequirementResponseParser().parse(raw_llm_response)
    assert parsed.analysis is not None

    validated = RequirementValidator().validate(parsed.analysis)
    known = validated.known_information

    assert known.garden == "HOOKMOL"
    assert known.seasons == [2025, 2026]
    assert "Sale 26" in (known.sale_range or "")
    assert "average price" in known.metrics
    assert known.output_grain == "garden-wise"
    assert known.report_type == "Garden Average Report"


def test_hookmol_flat_llm_response_maps_to_known_information() -> None:
    raw_llm_response = json.dumps(
        {
            "summary": "Garden average comparison report.",
            "reportType": "Garden Average Report",
            "garden": "HOOKMOL",
            "seasons": [2025, 2026],
            "saleRange": "up to Sale 26",
            "metrics": ["average price"],
            "grouping": "garden-wise",
        }
    )

    parsed = RequirementResponseParser().parse(raw_llm_response)

    assert parsed.analysis is not None
    known = parsed.analysis.known_information
    assert known.garden == "HOOKMOL"
    assert known.seasons == [2025, 2026]
    assert "Sale 26" in (known.sale_range or "")
    assert "average price" in known.metrics
    assert known.output_grain == "garden-wise"


def test_offline_fallback_extracts_hookmol_requirement() -> None:
    response = OfflineRequirementLLMClient().generate(
        "hookmol averages season 2025 vs 2026 upto sale 26"
    )

    parsed = RequirementResponseParser().parse(response)
    assert parsed.analysis is not None
    known = parsed.analysis.known_information

    assert known.garden == "HOOKMOL"
    assert known.seasons == [2025, 2026]
    assert known.sale_range == "up to sale 26"
    assert known.metrics == ["average price"]
    assert known.output_grain == "garden-wise"
    assert known.report_type == "Garden Average Report"
    assert parsed.analysis.metadata["llm_mode"] == "offline_fallback"


def test_orchestrator_with_offline_fallback_extracts_hookmol_requirement() -> None:
    orchestrator = RequirementUnderstandingOrchestrator(
        knowledge_loader=KnowledgeLoader(),
        prompt_builder=PromptBuilder(),
        llm_client=OfflineRequirementLLMClient(),
        response_parser=RequirementResponseParser(),
        requirement_validator=RequirementValidator(),
    )

    result = orchestrator.analyze(
        "hookmol averages season 2025 vs 2026 upto sale 26"
    )
    known = result.known_information

    assert known.garden == "HOOKMOL"
    assert known.seasons == [2025, 2026]
    assert known.sale_range == "up to sale 26"
    assert known.metrics == ["average price"]
    assert known.output_grain == "garden-wise"
    assert known.report_type == "Garden Average Report"
    assert result.sql_generation_allowed is False


def _offline_known(requirement: str):
    response = OfflineRequirementLLMClient().generate(requirement)
    parsed = RequirementResponseParser().parse(response)
    assert parsed.analysis is not None
    return RequirementValidator().validate(parsed.analysis).known_information


def test_offline_extracts_buyer_purchase_report() -> None:
    known = _offline_known(
        "buyer wise purchase report for HUL season 2026 sale 14 to 26"
    )

    assert known.buyer == "HINDUSTHAN UNILEVER LIMITED"
    assert known.season == 2026
    assert known.sale_range == "sale range 14 to 26"
    assert known.metrics == ["quantity", "value"]
    assert known.output_grain == "buyer-wise"
    assert known.report_type == "Buyer Purchase Report"


def test_offline_extracts_garden_ranking_report() -> None:
    known = _offline_known(
        "garden ranking for assam ctc est season 2026 upto sale 26"
    )

    assert known.area == "AS"
    assert known.category == "CTC"
    assert known.est_blf == "EST"
    assert known.season == 2026
    assert known.sale_range == "up to sale 26"
    assert known.metrics == ["ranking"]
    assert known.output_grain == "garden-wise"
    assert known.report_type == "Garden Ranking Report"


def test_offline_extracts_price_band_report() -> None:
    known = _offline_known(
        "price band report for dooars season 2025 sale 14 to 26"
    )

    assert known.area == "DO"
    assert known.season == 2025
    assert known.sale_range == "sale range 14 to 26"
    assert known.metrics == ["price band analysis"]
    assert known.report_type == "Price Band Report"


def test_offline_extracts_comparison_buying_report() -> None:
    known = _offline_known(
        "compare TCPL buying 2025 vs 2026 upto sale 26"
    )

    assert known.buyer == "TATA CONSUMER PRODUCTS LTD."
    assert known.seasons == [2025, 2026]
    assert known.sale_range == "up to sale 26"
    assert known.metrics == ["quantity", "value"]
    assert known.report_type == "Comparison Report"


def test_offline_sale_wise_average_does_not_extract_wise_as_garden() -> None:
    known = _offline_known(
        "sale wise average price for assam orthodox season 2026 sale 20"
    )

    assert known.area == "AS"
    assert known.category == "ORTHODOX"
    assert known.season == 2026
    assert known.sale_range == "sale 20"
    assert known.metrics == ["average price"]
    assert known.output_grain == "sale-wise"
    assert known.report_type == "Sale Wise Average Price Report"
    assert known.garden is None
