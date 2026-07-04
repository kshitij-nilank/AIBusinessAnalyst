"""Parse LLM JSON responses into requirement-engine models.

This module converts raw LLM response text into ``RequirementAnalysis``.
It validates schema conformance, reports malformed JSON, and exposes parse
errors without performing AI reasoning or business correction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from engine.common.llm_client import RawLLMResponse
from engine.requirement_engine.models import RequirementAnalysis


@dataclass(frozen=True, slots=True)
class ResponseParseError:
    """One parsing or validation error.

    Attributes:
        error_type: Error category, such as ``json_decode`` or ``validation``.
        message: Human-readable error message.
        location: Optional JSON/schema location.
        raw_detail: Optional machine-readable detail.
    """

    error_type: str
    message: str
    location: str | None = None
    raw_detail: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "error_type": self.error_type,
            "message": self.message,
            "location": self.location,
            "raw_detail": self.raw_detail,
        }


@dataclass(frozen=True, slots=True)
class ParsedRequirementAnalysis:
    """Result returned by ``RequirementResponseParser``.

    Attributes:
        analysis: Parsed ``RequirementAnalysis`` when parsing succeeds.
        errors: Parse and validation errors when parsing fails.
        raw_json: Extracted JSON text passed to Pydantic validation.
        raw_payload: Decoded JSON payload before model validation.
    """

    analysis: RequirementAnalysis | None
    errors: list[ResponseParseError] = field(default_factory=list)
    raw_json: str | None = None
    raw_payload: Any = None

    @property
    def ok(self) -> bool:
        """Return whether parsing and validation succeeded."""

        return self.analysis is not None and not self.errors

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "ok": self.ok,
            "analysis": self.analysis.model_dump(mode="json")
            if self.analysis is not None
            else None,
            "errors": [error.to_dict() for error in self.errors],
            "raw_json": self.raw_json,
            "raw_payload": self.raw_payload,
        }


class RequirementResponseParser:
    """Parser for converting LLM JSON output into ``RequirementAnalysis``.

    The parser accepts direct JSON, markdown-fenced JSON, or common raw provider
    envelopes. It does not invent missing fields, normalize business values, or
    change model data beyond Pydantic validation.
    """

    JSON_FENCE_PATTERN = re.compile(
        r"```(?:json)?\s*(?P<json>.*?)\s*```",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def parse(self, response: RawLLMResponse | str | bytes | dict[str, Any]) -> ParsedRequirementAnalysis:
        """Parse a raw response into ``RequirementAnalysis``.

        Args:
            response: Raw LLM response object, raw text, bytes, or already
                decoded JSON dictionary.
        """

        raw_text = self._coerce_to_text(response)
        if isinstance(response, dict):
            return self._validate_payload(response, raw_json=json.dumps(response))

        json_text = self._extract_json_text(raw_text)
        if not json_text:
            return ParsedRequirementAnalysis(
                analysis=None,
                errors=[
                    ResponseParseError(
                        error_type="empty_response",
                        message="Response did not contain JSON text.",
                    )
                ],
                raw_json=None,
            )

        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            return ParsedRequirementAnalysis(
                analysis=None,
                errors=[
                    ResponseParseError(
                        error_type="json_decode",
                        message=exc.msg,
                        location=f"line {exc.lineno}, column {exc.colno}",
                        raw_detail={"pos": exc.pos},
                    )
                ],
                raw_json=json_text,
            )

        extracted_payload = self._extract_provider_payload(payload)
        if extracted_payload is not payload:
            if isinstance(extracted_payload, str):
                return self.parse(extracted_payload)
            return self._validate_payload(extracted_payload, raw_json=json.dumps(extracted_payload))

        return self._validate_payload(payload, raw_json=json_text)

    def parse_or_raise(
        self,
        response: RawLLMResponse | str | bytes | dict[str, Any],
    ) -> RequirementAnalysis:
        """Parse a response or raise ``ValueError`` with parse details."""

        result = self.parse(response)
        if result.analysis is not None and not result.errors:
            return result.analysis

        messages = "; ".join(error.message for error in result.errors)
        raise ValueError(f"Failed to parse RequirementAnalysis: {messages}")

    def _validate_payload(
        self,
        payload: Any,
        *,
        raw_json: str | None,
    ) -> ParsedRequirementAnalysis:
        """Validate decoded JSON against the ``RequirementAnalysis`` schema."""

        try:
            payload = self._normalize_payload(payload)
            analysis = RequirementAnalysis.model_validate(payload)
        except ValidationError as exc:
            return ParsedRequirementAnalysis(
                analysis=None,
                errors=[
                    ResponseParseError(
                        error_type="validation",
                        message=error.get("msg", "Validation error"),
                        location=".".join(str(item) for item in error.get("loc", ())),
                        raw_detail=error,
                    )
                    for error in exc.errors()
                ],
                raw_json=raw_json,
                raw_payload=payload,
            )

        return ParsedRequirementAnalysis(
            analysis=analysis,
            errors=[],
            raw_json=raw_json,
            raw_payload=payload,
        )

    def _normalize_payload(self, payload: Any) -> Any:
        """Normalize common LLM JSON variants before schema validation."""

        if not isinstance(payload, dict):
            return payload

        payload = dict(payload)
        for wrapper_key in ("requirement_analysis", "requirementAnalysis", "analysis", "result"):
            wrapped = payload.get(wrapper_key)
            if isinstance(wrapped, dict):
                payload = dict(wrapped)
                break

        payload = _rename_keys(
            payload,
            {
                "requirementId": "requirement_id",
                "knownInformation": "known_information",
                "knownInfo": "known_information",
                "known": "known_information",
                "missingInformation": "missing_information",
                "clarificationQuestions": "clarification_questions",
                "businessRules": "business_rules",
                "candidateDatabaseObjects": "candidate_database_objects",
                "candidateObjects": "candidate_database_objects",
                "sqlGenerationAllowed": "sql_generation_allowed",
            },
        )

        if "summary" not in payload:
            payload["summary"] = payload.get("requirement_summary") or payload.get(
                "requirementSummary"
            ) or "Requirement analyzed."

        flat_known_information = self._extract_flat_known_information(payload)
        for key in flat_known_information:
            payload.pop(key, None)

        known_information = payload.get("known_information")
        if not isinstance(known_information, dict):
            known_information = {}
        known_information = {
            **flat_known_information,
            **known_information,
        }
        payload["known_information"] = self._normalize_known_information(
            known_information
        )

        payload.setdefault("missing_information", [])
        payload.setdefault("clarification_questions", [])
        payload.setdefault("business_rules", [])
        payload.setdefault("candidate_database_objects", [])
        payload.setdefault("assumptions", [])
        payload.setdefault("risks", [])
        payload.setdefault("sql_generation_allowed", False)
        payload.setdefault("metadata", {})
        return payload

    def _extract_flat_known_information(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Collect known-information fields returned at top level by an LLM."""

        known_aliases = {
            "business_objective",
            "businessObjective",
            "objective",
            "report_type",
            "reportType",
            "report",
            "season",
            "seasons",
            "financialYear",
            "financial_year",
            "sale_range",
            "saleRange",
            "saleNumber",
            "sale_number",
            "dateRange",
            "date_range",
            "uptoSale",
            "upToSale",
            "garden",
            "gardenName",
            "garden_name",
            "mark",
            "area",
            "centre",
            "category",
            "tea_type",
            "teaType",
            "sub_tea_type",
            "subTeaType",
            "est_blf",
            "estBlf",
            "lot_status",
            "lotStatus",
            "metrics",
            "metric",
            "grouping",
            "groupingLevel",
            "grouping_level",
            "grain",
            "output_grain",
            "outputGrain",
            "output_format",
            "outputFormat",
            "raw_request_text",
            "rawRequirement",
            "raw_request",
            "userRequirement",
        }
        return {
            key: value
            for key, value in payload.items()
            if key in known_aliases
        }

    def _normalize_known_information(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize known-information field names and simple value shapes."""

        normalized = _rename_keys(
            data,
            {
                "businessObjective": "business_objective",
                "objective": "business_objective",
                "reportType": "report_type",
                "report": "report_type",
                "financialYear": "season",
                "financial_year": "season",
                "saleRange": "sale_range",
                "saleNumber": "sale_range",
                "sale_number": "sale_range",
                "dateRange": "sale_range",
                "date_range": "sale_range",
                "uptoSale": "sale_range",
                "upToSale": "sale_range",
                "gardenName": "garden",
                "garden_name": "garden",
                "mark": "garden",
                "teaType": "tea_type",
                "tea_type": "tea_type",
                "subTeaType": "sub_tea_type",
                "sub_tea_type": "sub_tea_type",
                "estBlf": "est_blf",
                "est_blf": "est_blf",
                "lotStatus": "lot_status",
                "lot_status": "lot_status",
                "metric": "metrics",
                "grouping": "output_grain",
                "groupingLevel": "output_grain",
                "grouping_level": "output_grain",
                "grain": "output_grain",
                "outputGrain": "output_grain",
                "outputFormat": "output_format",
                "rawRequirement": "raw_request_text",
                "raw_request": "raw_request_text",
                "userRequirement": "raw_request_text",
            },
        )

        if "seasons" not in normalized and "season" in normalized:
            seasons = _extract_years(normalized.get("season"))
            if len(seasons) > 1:
                normalized["seasons"] = seasons
                normalized["season"] = None

        if "seasons" in normalized:
            normalized["seasons"] = _extract_years(normalized["seasons"])

        if isinstance(normalized.get("season"), str):
            years = _extract_years(normalized["season"])
            normalized["season"] = years[0] if len(years) == 1 else None
            if len(years) > 1 and not normalized.get("seasons"):
                normalized["seasons"] = years

        if "metrics" in normalized:
            normalized["metrics"] = _ensure_list(normalized["metrics"])

        if isinstance(normalized.get("garden"), str):
            normalized["garden"] = normalized["garden"].strip().upper()

        return normalized

    def _coerce_to_text(self, response: RawLLMResponse | str | bytes | dict[str, Any]) -> str:
        """Convert supported response inputs to text."""

        if isinstance(response, RawLLMResponse):
            return response.body
        if isinstance(response, bytes):
            return response.decode("utf-8", errors="replace")
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return json.dumps(response)
        return str(response)

    def _extract_json_text(self, raw_text: str) -> str:
        """Extract JSON text from raw text or markdown fenced JSON."""

        text = raw_text.strip()
        if not text:
            return ""

        if text.startswith("{") or text.startswith("["):
            return text

        fence_match = self.JSON_FENCE_PATTERN.search(text)
        if fence_match:
            return fence_match.group("json").strip()

        first_object = text.find("{")
        last_object = text.rfind("}")
        if first_object != -1 and last_object > first_object:
            return text[first_object : last_object + 1]

        return text

    def _extract_provider_payload(self, payload: Any) -> Any:
        """Extract likely assistant JSON content from common provider envelopes."""

        if not isinstance(payload, dict):
            return payload

        openai_content = self._extract_openai_content(payload)
        if openai_content is not None:
            return openai_content

        gemini_content = self._extract_gemini_content(payload)
        if gemini_content is not None:
            return gemini_content

        local_content = self._extract_local_content(payload)
        if local_content is not None:
            return local_content

        return payload

    @staticmethod
    def _extract_openai_content(payload: dict[str, Any]) -> str | None:
        """Extract assistant content from an OpenAI-compatible envelope."""

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None

        message = first_choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]

        if isinstance(first_choice.get("text"), str):
            return first_choice["text"]

        return None

    @staticmethod
    def _extract_gemini_content(payload: dict[str, Any]) -> str | None:
        """Extract text content from a Gemini-style envelope."""

        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return None

        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            return None

        text_parts = [
            part.get("text")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "\n".join(text_parts) if text_parts else None

    @staticmethod
    def _extract_local_content(payload: dict[str, Any]) -> str | dict[str, Any] | None:
        """Extract content from common local-model response shapes."""

        for key in ("response", "content", "output"):
            value = payload.get(key)
            if isinstance(value, (str, dict)):
                return value
        return None


def _rename_keys(data: dict[str, Any], key_map: dict[str, str]) -> dict[str, Any]:
    """Return a copy of a dictionary with known aliases renamed."""

    normalized: dict[str, Any] = {}
    for key, value in data.items():
        normalized[key_map.get(key, key)] = value
    return normalized


def _ensure_list(value: Any) -> list[Any]:
    """Return value as a list while preserving existing list contents."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _extract_years(value: Any) -> list[int]:
    """Extract four-digit years from common scalar or list shapes."""

    values = _ensure_list(value)
    years: list[int] = []
    for item in values:
        if isinstance(item, int):
            years.append(item)
            continue
        for match in re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", str(item)):
            years.append(int(match))
    return list(dict.fromkeys(years))
