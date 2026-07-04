import json
import os

import main
from engine.requirement_engine.response_parser import RequirementResponseParser


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
