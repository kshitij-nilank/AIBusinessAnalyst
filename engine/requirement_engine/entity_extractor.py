"""Deterministic entity extraction for common Parcon requirements."""

from __future__ import annotations

import re
from typing import Any


class EntityExtractor:
    """Extract structured business entities from plain requirement text."""

    AREA_ALIASES = {
        "assam": "AS",
        "dooars": "DO",
        "terai": "TR",
        "cachar": "CA",
        "tripura": "TP",
    }
    BUYER_ALIASES = {
        "hul": "HINDUSTHAN UNILEVER LIMITED",
        "tcpl": "TATA CONSUMER PRODUCTS LTD.",
    }
    STOP_WORDS = {
        "give",
        "show",
        "need",
        "report",
        "garden",
        "gardens",
        "average",
        "averages",
        "avg",
        "price",
        "season",
        "vs",
        "compare",
        "upto",
        "up",
        "to",
        "sale",
        "wise",
        "for",
        "of",
        "the",
        "and",
        "buyer",
        "purchase",
        "buying",
        "ranking",
        "rank",
        "band",
        "ctc",
        "orthodox",
        "leaf",
        "dust",
        "est",
        "blf",
        "assam",
        "dooars",
        "terai",
        "cachar",
        "tripura",
    }

    def extract(self, text: str) -> dict[str, Any]:
        """Extract known-information fields from requirement text."""

        return {
            "seasons": self.extract_seasons(text),
            "sale_range": self.extract_sale_range(text),
            "area": self.extract_area(text),
            "category": self.extract_category(text),
            "tea_type": self.extract_tea_type(text),
            "est_blf": self.extract_est_blf(text),
            "buyer": self.extract_buyer(text),
            "garden": self.extract_garden(text),
            "metrics": self.extract_metrics(text),
            "output_grain": self.extract_grouping(text),
        }

    def extract_seasons(self, text: str) -> list[int]:
        """Extract year-like season values."""

        years = [int(match) for match in re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", text)]
        return list(dict.fromkeys(years))

    def extract_sale_range(self, text: str) -> str | None:
        """Extract sale range phrases."""

        normalized = text.casefold()

        range_match = re.search(
            r"\bsale\s*(\d+)\s*(?:to|-)\s*(\d+)\b",
            normalized,
        )
        if range_match:
            return f"sale range {range_match.group(1)} to {range_match.group(2)}"

        upto_match = re.search(
            r"\b(?:up\s*to|upto)\s*sale\s*(\d+)\b",
            normalized,
        )
        if upto_match:
            return f"up to sale {upto_match.group(1)}"

        single_match = re.search(r"\bsale\s*(\d+)\b", normalized)
        if single_match:
            return f"sale {single_match.group(1)}"

        return None

    def extract_area(self, text: str) -> str | None:
        """Extract area alias."""

        normalized = text.casefold()
        if re.search(r"\bdooars\s*/\s*terai\b|\bdooars\s+terai\b", normalized):
            return "DO/TR"
        for name, code in self.AREA_ALIASES.items():
            if re.search(rf"\b{name}\b", normalized):
                return code
        return None

    def extract_category(self, text: str) -> str | None:
        """Extract tea category."""

        normalized = text.casefold()
        if re.search(r"\bctc\b", normalized):
            return "CTC"
        if re.search(r"\borthodox\b", normalized):
            return "ORTHODOX"
        return None

    def extract_tea_type(self, text: str) -> str | None:
        """Extract tea type."""

        normalized = text.casefold()
        if re.search(r"\bleaf\b", normalized):
            return "LEAF"
        if re.search(r"\bdust\b", normalized):
            return "DUST"
        return None

    def extract_est_blf(self, text: str) -> str | None:
        """Extract EST/BLF filter."""

        normalized = text.casefold()
        if re.search(r"\best\b", normalized):
            return "EST"
        if re.search(r"\bblf\b", normalized):
            return "BLF"
        return None

    def extract_buyer(self, text: str) -> str | None:
        """Extract known buyer alias."""

        normalized = text.casefold()
        for alias, buyer in self.BUYER_ALIASES.items():
            if re.search(rf"\b{alias}\b", normalized):
                return buyer
        return None

    def extract_garden(self, text: str) -> str | None:
        """Extract likely garden name without treating grouping words as gardens."""

        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)
        if not tokens:
            return None

        for index, token in enumerate(tokens):
            if token.casefold() in {"average", "averages", "avg"}:
                for candidate in reversed(tokens[:index]):
                    if self._is_garden_candidate(candidate):
                        return candidate.upper()

        for index, token in enumerate(tokens):
            if token.casefold() == "garden":
                for candidate in reversed(tokens[:index]):
                    if self._is_garden_candidate(candidate):
                        return candidate.upper()

        return None

    def extract_metrics(self, text: str) -> list[str]:
        """Extract requested metrics."""

        normalized = text.casefold()
        metrics: list[str] = []
        if re.search(r"\b(avg|average|averages)\b", normalized) or "average price" in normalized:
            metrics.append("average price")
        if re.search(r"\b(purchase|buying)\b", normalized):
            metrics.extend(["quantity", "value"])
        if re.search(r"\b(ranking|rank)\b", normalized):
            metrics.append("ranking")
        if "price band" in normalized:
            metrics.append("price band analysis")
        return list(dict.fromkeys(metrics))

    def extract_grouping(self, text: str) -> str | None:
        """Extract grouping level."""

        normalized = text.casefold()
        for key, value in {
            "garden": "garden-wise",
            "buyer": "buyer-wise",
            "sale": "sale-wise",
            "grade": "grade-wise",
            "area": "area-wise",
        }.items():
            if re.search(rf"\b{key}\s*[- ]?wise\b", normalized):
                return value

        if re.search(r"\bgarden\s+(ranking|rank|average|averages)\b", normalized):
            return "garden-wise"
        if self.extract_garden(text):
            return "garden-wise"
        return None

    def _is_garden_candidate(self, token: str) -> bool:
        """Return whether a token can plausibly be a garden name."""

        normalized = token.casefold()
        return normalized not in self.STOP_WORDS and normalized not in self.BUYER_ALIASES
