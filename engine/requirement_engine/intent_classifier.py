"""Deterministic intent classification for common Parcon requirements."""

from __future__ import annotations

import re


class IntentClassifier:
    """Classify common report intents from requirement text."""

    def classify(self, text: str) -> str | None:
        """Return a report type when a known intent is detected."""

        normalized = _normalize(text)

        if re.search(r"\bsale\s*[- ]?wise\b", normalized) and "average price" in normalized:
            return "Sale Wise Average Price Report"
        if re.search(r"\bsale\s*[- ]?wise\b", normalized) and re.search(
            r"\b(avg|average|averages)\b", normalized
        ):
            return "Sale Wise Average Price Report"
        if "price band" in normalized:
            return "Price Band Report"
        if "garden ranking" in normalized or "garden rank" in normalized:
            return "Garden Ranking Report"
        if re.search(r"\bbuyer\s*[- ]?wise\b", normalized) and re.search(
            r"\b(purchase|buying)\b", normalized
        ):
            return "Buyer Purchase Report"
        if "garden average" in normalized or re.search(
            r"\b(avg|average|averages)\b", normalized
        ):
            return "Garden Average Report"
        if "compare" in normalized or re.search(r"\bvs\b", normalized):
            return "Comparison Report"
        return None


def _normalize(text: str) -> str:
    """Normalize text for rule matching."""

    return re.sub(r"\s+", " ", text.casefold()).strip()
