"""Resolve applicable business rules for a RequirementAnalysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from engine.requirement_engine.models import (
    BusinessRuleResolution,
    RequirementAnalysis,
    ResolvedBusinessRule,
)


@dataclass(frozen=True, slots=True)
class BusinessRuleIndexEntry:
    """Indexed metadata for one business-rule markdown file."""

    rule_id: str
    name: str
    file_path: str
    keywords: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)
    report_types: set[str] = field(default_factory=set)
    metrics: set[str] = field(default_factory=set)


class BusinessRuleResolver:
    """Resolve business rules from ``knowledge/business`` for a requirement."""

    RULE_METADATA: dict[str, dict[str, set[str]]] = {
        "BR-001": {"keywords": {"fyear", "financial", "year", "season"}},
        "BR-002": {"keywords": {"sale", "salealias", "sale number", "sale range"}},
        "BR-003": {"keywords": {"area", "assam", "dooars", "terai", "cachar", "tripura"}},
        "BR-004": {"keywords": {"offer", "offer quantity", "quantity"}, "metrics": {"quantity"}},
        "BR-005": {"keywords": {"sold", "sold quantity", "quantity"}, "metrics": {"quantity"}},
        "BR-006": {"keywords": {"average", "average price", "avg"}, "metrics": {"average price"}},
        "BR-007": {"keywords": {"price band"}, "metrics": {"price band analysis"}},
        "BR-009": {"keywords": {"est", "blf"}, "entities": {"est_blf"}},
        "BR-010": {"keywords": {"tea type", "leaf", "dust"}, "entities": {"tea_type"}},
        "BR-015": {"keywords": {"buyer", "buyer group"}, "entities": {"buyer"}},
        "BR-017": {
            "keywords": {"garden ranking", "ranking"},
            "report_types": {"Garden Ranking Report"},
            "metrics": {"ranking"},
        },
        "BR-018": {
            "keywords": {"buyer ranking", "ranking"},
            "report_types": {"Buyer Ranking Report"},
            "metrics": {"ranking"},
        },
        "BR-019": {"keywords": {"financial year", "fyear", "season"}},
        "BR-020": {"keywords": {"season"}},
        "BR-021": {"keywords": {"sale number", "sale range", "sale"}},
        "BR-022": {"keywords": {"centre", "center"}},
        "BR-024": {"keywords": {"filters", "report filters"}},
        "BR-025": {"keywords": {"validation", "data validation"}},
        "BR-027": {"keywords": {"historical", "comparison", "vs"}, "report_types": {"Comparison Report"}},
        "BR-030": {"keywords": {"reporting", "standards"}},
    }

    def __init__(self, business_rules_path: Path | str = "knowledge/business") -> None:
        """Create a resolver for a business-rule folder."""

        self.business_rules_path = Path(business_rules_path)
        self._index: dict[str, BusinessRuleIndexEntry] | None = None

    def resolve(self, analysis: RequirementAnalysis) -> BusinessRuleResolution:
        """Return applicable business rules for a requirement analysis."""

        applicable: list[ResolvedBusinessRule] = []
        missing_dependencies: list[str] = []
        context = self._requirement_context(analysis)

        for entry in self.index_rules().values():
            reasons = self._match_reasons(entry, context)
            dependencies = self._missing_dependencies(entry, analysis)
            if reasons:
                applicable.append(
                    ResolvedBusinessRule(
                        rule_id=entry.rule_id,
                        name=entry.name,
                        file_path=entry.file_path,
                        keywords=sorted(entry.keywords),
                        entities=sorted(entry.entities),
                        report_types=sorted(entry.report_types),
                        metrics=sorted(entry.metrics),
                        applies_because=reasons,
                        missing_dependencies=dependencies,
                    )
                )
                missing_dependencies.extend(dependencies)

        return BusinessRuleResolution(
            applicable_rules=applicable,
            missing_rule_dependencies=sorted(set(missing_dependencies)),
        )

    def index_rules(self) -> dict[str, BusinessRuleIndexEntry]:
        """Index rule files by rule ID."""

        if self._index is not None:
            return self._index

        index: dict[str, BusinessRuleIndexEntry] = {}
        if not self.business_rules_path.exists():
            self._index = index
            return index

        for path in sorted(self.business_rules_path.glob("BR-*.md")):
            rule_id, name = self._parse_rule_file_name(path)
            metadata = self.RULE_METADATA.get(rule_id, {})
            derived_keywords = set(_split_identifier(name))
            derived_keywords.add(name.casefold().replace("_", " "))
            index[rule_id] = BusinessRuleIndexEntry(
                rule_id=rule_id,
                name=name.replace("_", " "),
                file_path=path.as_posix(),
                keywords=derived_keywords | metadata.get("keywords", set()),
                entities=metadata.get("entities", set()),
                report_types=metadata.get("report_types", set()),
                metrics=metadata.get("metrics", set()),
            )

        self._index = index
        return index

    def _match_reasons(
        self,
        entry: BusinessRuleIndexEntry,
        context: dict[str, set[str]],
    ) -> list[str]:
        """Return reasons why a rule matches the requirement context."""

        reasons: list[str] = []
        if entry.report_types and not entry.report_types & context["report_types"]:
            return reasons

        for metric in sorted(entry.metrics & context["metrics"]):
            reasons.append(f"Metric requires rule: {metric}")
        for report_type in sorted(entry.report_types & context["report_types"]):
            reasons.append(f"Report type requires rule: {report_type}")
        for entity in sorted(entry.entities & context["entities"]):
            reasons.append(f"Entity requires rule: {entity}")
        for keyword in sorted(entry.keywords & context["keywords"]):
            reasons.append(f"Keyword matched: {keyword}")
        return reasons

    def _missing_dependencies(
        self,
        entry: BusinessRuleIndexEntry,
        analysis: RequirementAnalysis,
    ) -> list[str]:
        """Return rule dependencies missing from the current requirement."""

        known = analysis.known_information
        missing: list[str] = []

        if entry.rule_id in {"BR-002", "BR-021"} and not known.sale_range:
            missing.append("sale_range")
        if entry.rule_id in {"BR-001", "BR-019", "BR-020"} and not (
            known.season or known.seasons
        ):
            missing.append("season")
        if entry.rule_id == "BR-003" and not known.area:
            missing.append("area")
        if entry.rule_id == "BR-009" and not known.est_blf:
            missing.append("est_blf")
        if entry.rule_id == "BR-010" and not known.tea_type:
            missing.append("tea_type")
        return missing

    def _requirement_context(self, analysis: RequirementAnalysis) -> dict[str, set[str]]:
        """Build comparable requirement context sets."""

        known = analysis.known_information
        keywords = set(_split_identifier(known.raw_request_text or ""))
        keywords.update(_split_identifier(known.report_type or ""))
        keywords.update(_split_identifier(known.sale_range or ""))
        keywords.update(metric.casefold() for metric in known.metrics)

        entities = {
            name
            for name, value in {
                "garden": known.garden,
                "buyer": known.buyer,
                "area": known.area,
                "category": known.category,
                "tea_type": known.tea_type,
                "est_blf": known.est_blf,
            }.items()
            if value
        }
        return {
            "keywords": keywords,
            "entities": entities,
            "report_types": {known.report_type} if known.report_type else set(),
            "metrics": {metric.casefold() for metric in known.metrics},
        }

    @staticmethod
    def _parse_rule_file_name(path: Path) -> tuple[str, str]:
        """Parse BR-### and rule name from a filename."""

        match = re.match(r"^(BR-\d+)_(.+)$", path.stem)
        if not match:
            return path.stem, path.stem
        return match.group(1), match.group(2)


def _split_identifier(value: str) -> set[str]:
    """Split identifiers and plain text into lowercase keywords."""

    return {
        token.casefold()
        for token in re.split(r"[^A-Za-z0-9/]+", value)
        if token
    }
