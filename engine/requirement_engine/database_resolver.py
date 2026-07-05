"""Resolve likely database objects for a RequirementAnalysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from engine.requirement_engine.models import (
    CandidateDatabaseObject,
    DatabaseObjectType,
    DatabaseResolution,
    RequirementAnalysis,
    RequirementFieldStatus,
)


@dataclass(frozen=True, slots=True)
class DatabaseSchemaEntry:
    """Parsed database schema entry."""

    object_name: str
    purpose: str = "Unknown"
    important_columns: list[str] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)


class DatabaseResolver:
    """Map analyzed requirements to likely tables/views."""

    def __init__(self, schema_path: Path | str = "knowledge/database/database_schema.md") -> None:
        """Create a resolver using a database schema markdown file."""

        self.schema_path = Path(schema_path)
        self._entries: list[DatabaseSchemaEntry] | None = None

    def resolve(self, analysis: RequirementAnalysis) -> DatabaseResolution:
        """Return likely database objects for a requirement."""

        entries = self.load_schema_entries()
        candidates: list[CandidateDatabaseObject] = []
        missing_dependencies: list[str] = []

        for entry in entries:
            score, reasons = self._score_entry(entry, analysis)
            if score <= 0:
                continue

            candidates.append(
                CandidateDatabaseObject(
                    object_name=entry.object_name,
                    object_type=self._object_type(entry.object_name),
                    purpose="; ".join(reasons) if reasons else entry.purpose,
                    important_columns=entry.important_columns,
                    join_keys=entry.joins,
                    filters=entry.filters,
                    confidence=RequirementFieldStatus.PROVIDED
                    if score >= 3
                    else RequirementFieldStatus.ASSUMED,
                )
            )

        if not candidates:
            missing_dependencies.append("database_object")

        return DatabaseResolution(
            candidate_database_objects=candidates,
            missing_dependencies=missing_dependencies,
        )

    def load_schema_entries(self) -> list[DatabaseSchemaEntry]:
        """Parse database schema markdown into entries."""

        if self._entries is not None:
            return self._entries
        if not self.schema_path.exists():
            self._entries = []
            return []

        content = self.schema_path.read_text(encoding="utf-8")
        sections = re.split(r"(?m)^##\s+`([^`]+)`\s*$", content)
        entries: list[DatabaseSchemaEntry] = []
        for index in range(1, len(sections), 2):
            object_name = sections[index].strip()
            body = sections[index + 1]
            entries.append(
                DatabaseSchemaEntry(
                    object_name=object_name,
                    purpose=self._extract_heading_text(body, "Purpose") or "Unknown",
                    important_columns=self._extract_bullets(body, "Important Columns"),
                    joins=self._extract_bullets(body, "Joins"),
                    filters=self._extract_bullets(body, "Frequently Used Filters"),
                )
            )

        self._entries = entries
        return entries

    def _score_entry(
        self,
        entry: DatabaseSchemaEntry,
        analysis: RequirementAnalysis,
    ) -> tuple[int, list[str]]:
        """Score one schema entry against a requirement."""

        known = analysis.known_information
        object_lower = entry.object_name.casefold()
        haystack = " ".join(
            [entry.object_name, entry.purpose, *entry.important_columns, *entry.filters]
        ).casefold()
        score = 0
        reasons: list[str] = []

        if "saletransactionview" in object_lower:
            score += 1
            reasons.append("Primary auction sale transaction source")
        if known.report_type and any(
            word in known.report_type.casefold()
            for word in ("garden", "buyer", "sale", "ranking", "average", "price band")
        ) and "saletransactionview" in object_lower:
            score += 2
            reasons.append(f"Supports report type: {known.report_type}")
        if known.buyer and "buyergroup" in object_lower:
            score += 2
            reasons.append("Buyer-specific report may need buyer group lookup")
        if "teainnovation" in object_lower or "tc_tasting" in object_lower:
            if known.report_type and "tasting" in known.report_type.casefold():
                score += 2
                reasons.append("Tasting report source")
        for metric in known.metrics:
            if metric.casefold() in haystack:
                score += 1
                reasons.append(f"Schema mentions metric: {metric}")
        if known.garden and _contains_schema_term(haystack, "garden"):
            score += 1
            reasons.append("Schema supports garden-level filtering")
        if known.buyer and _contains_schema_term(haystack, "buyer"):
            score += 1
            reasons.append("Schema supports buyer-level filtering")
        if known.area and _contains_schema_term(haystack, "area"):
            score += 1
            reasons.append("Schema supports area filtering")
        if known.category and _contains_schema_term(haystack, "category"):
            score += 1
            reasons.append("Schema supports category filtering")
        if known.est_blf and _contains_schema_term(haystack, "est"):
            score += 1
            reasons.append("Schema supports EST/BLF filtering")

        return score, reasons

    @staticmethod
    def _object_type(object_name: str) -> DatabaseObjectType:
        """Infer database object type from name."""

        if "INFORMATION_SCHEMA" in object_name:
            return DatabaseObjectType.METADATA_VIEW
        if object_name.casefold().endswith("view"):
            return DatabaseObjectType.VIEW
        return DatabaseObjectType.TABLE

    @staticmethod
    def _extract_heading_text(body: str, heading: str) -> str | None:
        """Extract text below a markdown heading until the next heading."""

        match = re.search(
            rf"(?ms)^###\s+{re.escape(heading)}\s*\n(.*?)(?=^###\s+|\Z)",
            body,
        )
        if not match:
            return None
        return match.group(1).strip()

    def _extract_bullets(self, body: str, heading: str) -> list[str]:
        """Extract bullet values below a markdown heading."""

        section = self._extract_heading_text(body, heading)
        if not section:
            return []
        return [
            line.strip()[2:].strip("`")
            for line in section.splitlines()
            if line.strip().startswith("- ")
        ]


def _contains_schema_term(haystack: str, term: str) -> bool:
    """Return whether a schema term appears as a whole word."""

    return bool(re.search(rf"\b{re.escape(term.casefold())}\b", haystack))
