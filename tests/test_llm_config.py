import os
from tempfile import TemporaryDirectory

from engine.common.config import load_environment
from engine.common.llm_client import LLMClient, LLMConfig, LLMProvider
from engine.requirement_engine.models import KnownInformation
from engine.requirement_engine.prompt_builder import (
    DefaultRequirementPromptTemplate,
    PromptBuilder,
)


def test_load_environment_overrides_existing_values() -> None:
    original = os.environ.get("LLM_MODEL")
    os.environ["LLM_MODEL"] = "from_shell"
    try:
        with TemporaryDirectory() as directory:
            env_file = os.path.join(directory, ".env")
            with open(env_file, "w", encoding="utf-8") as handle:
                handle.write("LLM_MODEL=from_dotenv\n")

            loaded = load_environment(env_file)
            assert loaded is True
            assert os.environ["LLM_MODEL"] == "from_dotenv"
    finally:
        if original is None:
            os.environ.pop("LLM_MODEL", None)
        else:
            os.environ["LLM_MODEL"] = original


def test_openai_base_url_builds_chat_completions_endpoint() -> None:
    client = LLMClient(
        LLMConfig(
            provider=LLMProvider.OPENAI,
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            api_key="test-key",
        )
    )

    assert client.endpoint_url == "https://api.openai.com/v1/chat/completions"


def test_prompt_template_mentions_json() -> None:
    assert "JSON" in DefaultRequirementPromptTemplate.RESPONSE_INSTRUCTIONS


def test_prompt_builder_includes_user_requirement() -> None:
    requirement = "GIVE HOOKMOL GARDEN AVERAGES FOR SEASON 2025 VS 2026 UPTO SALE 26"

    prompt = PromptBuilder().build(
        user_requirement=requirement,
        business_rules=[],
        database_knowledge=[],
        thinking_layer=[],
    )

    assert requirement in prompt.prompt


def test_known_information_supports_expected_garden_comparison_fields() -> None:
    info = KnownInformation(
        garden="HOOKMOL",
        seasons=[2025, 2026],
        sale_range="up to sale 26",
        metrics=["average price"],
        output_grain="garden-wise",
    )

    assert info.garden == "HOOKMOL"
    assert info.seasons == [2025, 2026]
