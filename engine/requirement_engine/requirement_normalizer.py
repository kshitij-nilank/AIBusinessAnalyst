"""Normalize extracted requirement text into RequirementAnalysis JSON shape."""

from __future__ import annotations

from typing import Any

from engine.requirement_engine.entity_extractor import EntityExtractor
from engine.requirement_engine.intent_classifier import IntentClassifier


class RequirementNormalizer:
    """Build parser-compatible RequirementAnalysis payloads from text."""

    def __init__(
        self,
        entity_extractor: EntityExtractor | None = None,
        intent_classifier: IntentClassifier | None = None,
    ) -> None:
        """Create a normalizer with injectable deterministic components."""

        self.entity_extractor = entity_extractor or EntityExtractor()
        self.intent_classifier = intent_classifier or IntentClassifier()

    def normalize(self, requirement_text: str) -> dict[str, Any]:
        """Return a RequirementAnalysis-compatible dictionary."""

        text = requirement_text.strip()
        entities = self.entity_extractor.extract(text)
        report_type = self.intent_classifier.classify(text)
        grouping = entities.get("output_grain")
        seasons = entities.get("seasons") or []

        if not grouping and report_type in {"Garden Ranking Report", "Garden Average Report"}:
            grouping = "garden-wise"

        known_information = {
            "business_objective": None,
            "stakeholder": None,
            "report_type": report_type,
            "season": seasons[0] if len(seasons) == 1 else None,
            "seasons": seasons,
            "sale_range": entities.get("sale_range"),
            "garden": entities.get("garden"),
            "buyer": entities.get("buyer"),
            "area": entities.get("area"),
            "centre": None,
            "category": entities.get("category"),
            "tea_type": entities.get("tea_type"),
            "sub_tea_type": None,
            "est_blf": entities.get("est_blf"),
            "lot_status": None,
            "metrics": entities.get("metrics") or [],
            "output_grain": grouping,
            "output_format": None,
            "raw_request_text": text,
        }

        return {
            "summary": report_type or "Requirement received for analysis.",
            "known_information": known_information,
            "metadata": {
                "confidence_score": 0.65,
                "llm_mode": "offline_fallback",
                "fallback_reason": "Offline fallback used because LLM API is unavailable.",
            },
        }
