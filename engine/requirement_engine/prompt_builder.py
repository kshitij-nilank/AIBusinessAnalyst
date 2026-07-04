"""Prompt assembly utilities for the requirement engine.

This module builds prompt text from user requirements and loaded knowledge.
It does not call an LLM, perform AI reasoning, validate business rules, or
generate SQL. Its only responsibility is deterministic prompt assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence

from engine.requirement_engine.knowledge_loader import (
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeSection,
)


class PromptSectionName(str, Enum):
    """Canonical section names used in assembled prompts."""

    SYSTEM_INSTRUCTIONS = "system_instructions"
    THINKING_LAYER = "thinking_layer"
    BUSINESS_RULES = "business_rules"
    DATABASE_KNOWLEDGE = "database_knowledge"
    REQUIREMENT_ENGINE = "requirement_engine"
    USER_REQUIREMENT = "user_requirement"
    RESPONSE_INSTRUCTIONS = "response_instructions"


@dataclass(frozen=True, slots=True)
class PromptSection:
    """One named section in a final prompt.

    Attributes:
        name: Canonical prompt section identifier.
        title: Human-readable heading rendered in the prompt.
        content: Section body text.
    """

    name: PromptSectionName
    title: str
    content: str

    def render(self) -> str:
        """Render this section as markdown."""

        return f"## {self.title}\n\n{self.content.strip()}".strip()


@dataclass(frozen=True, slots=True)
class BuiltPrompt:
    """Final assembled prompt and its source sections.

    Attributes:
        prompt: Rendered prompt text.
        sections: Ordered sections used to build the prompt.
        metadata: Optional assembly metadata for orchestration or logging.
    """

    prompt: str
    sections: tuple[PromptSection, ...]
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary representation."""

        return {
            "prompt": self.prompt,
            "sections": [
                {
                    "name": section.name.value,
                    "title": section.title,
                    "content": section.content,
                }
                for section in self.sections
            ],
            "metadata": dict(self.metadata),
        }


class PromptTemplate(Protocol):
    """Protocol for prompt templates.

    Future file-backed, database-backed, or model-specific templates should
    implement this contract so orchestration code can keep calling
    ``PromptBuilder.build`` without changes.
    """

    def build(
        self,
        user_requirement: str,
        business_rules: Sequence[KnowledgeDocument | str],
        database_knowledge: Sequence[KnowledgeDocument | str],
        thinking_layer: Sequence[KnowledgeDocument | str],
        requirement_engine_knowledge: Sequence[KnowledgeDocument | str] = (),
    ) -> BuiltPrompt:
        """Build and return the final prompt."""


class DefaultRequirementPromptTemplate:
    """Default prompt template for requirement analysis.

    The order is intentionally fixed:
    1. System instructions
    2. Thinking layer
    3. Business rules
    4. Database knowledge
    5. Requirement-engine knowledge
    6. User requirement
    7. Response instructions
    """

    SYSTEM_INSTRUCTIONS = """You are the AI Business Analyst for Parcon.
Act like a Senior Business Analyst first and a SQL generator second.
Understand the requirement, identify missing information, and decide whether SQL generation is allowed.
Do not write SQL unless the requirement is complete and SQL generation is explicitly allowed."""

    RESPONSE_INSTRUCTIONS = """Return a structured requirement analysis.
Include requirement summary, known information, missing information, clarification questions, applicable business rules, candidate database objects, assumptions, risks, and whether SQL generation is allowed.
If any mandatory information is missing, ask clarification questions instead of generating SQL."""

    def build(
        self,
        user_requirement: str,
        business_rules: Sequence[KnowledgeDocument | str],
        database_knowledge: Sequence[KnowledgeDocument | str],
        thinking_layer: Sequence[KnowledgeDocument | str],
        requirement_engine_knowledge: Sequence[KnowledgeDocument | str] = (),
    ) -> BuiltPrompt:
        """Build a requirement-analysis prompt from supplied inputs."""

        sections = (
            PromptSection(
                name=PromptSectionName.SYSTEM_INSTRUCTIONS,
                title="System Instructions",
                content=self.SYSTEM_INSTRUCTIONS,
            ),
            PromptSection(
                name=PromptSectionName.THINKING_LAYER,
                title="Thinking Layer",
                content=_render_knowledge_items(thinking_layer),
            ),
            PromptSection(
                name=PromptSectionName.BUSINESS_RULES,
                title="Business Rules",
                content=_render_knowledge_items(business_rules),
            ),
            PromptSection(
                name=PromptSectionName.DATABASE_KNOWLEDGE,
                title="Database Knowledge",
                content=_render_knowledge_items(database_knowledge),
            ),
            PromptSection(
                name=PromptSectionName.REQUIREMENT_ENGINE,
                title="Requirement Engine Knowledge",
                content=_render_knowledge_items(requirement_engine_knowledge),
            ),
            PromptSection(
                name=PromptSectionName.USER_REQUIREMENT,
                title="User Requirement",
                content=user_requirement,
            ),
            PromptSection(
                name=PromptSectionName.RESPONSE_INSTRUCTIONS,
                title="Response Instructions",
                content=self.RESPONSE_INSTRUCTIONS,
            ),
        )

        rendered_prompt = "\n\n---\n\n".join(section.render() for section in sections)
        return BuiltPrompt(
            prompt=rendered_prompt,
            sections=sections,
            metadata={
                "template": self.__class__.__name__,
                "section_count": len(sections),
            },
        )


class PromptBuilder:
    """Facade for deterministic prompt assembly.

    The builder accepts a prompt template through dependency injection. This
    keeps orchestration code stable when templates move to markdown files,
    vector stores, or provider-specific formats in the future.
    """

    def __init__(self, template: PromptTemplate | None = None) -> None:
        """Create a prompt builder using the provided template."""

        self.template = template or DefaultRequirementPromptTemplate()

    def build(
        self,
        user_requirement: str,
        business_rules: Sequence[KnowledgeDocument | str],
        database_knowledge: Sequence[KnowledgeDocument | str],
        thinking_layer: Sequence[KnowledgeDocument | str],
        requirement_engine_knowledge: Sequence[KnowledgeDocument | str] = (),
    ) -> BuiltPrompt:
        """Assemble the final prompt in the template-defined order."""

        return self.template.build(
            user_requirement=user_requirement,
            business_rules=business_rules,
            database_knowledge=database_knowledge,
            thinking_layer=thinking_layer,
            requirement_engine_knowledge=requirement_engine_knowledge,
        )

    def build_from_collection(
        self,
        user_requirement: str,
        knowledge: KnowledgeCollection,
    ) -> BuiltPrompt:
        """Build a prompt directly from a loaded ``KnowledgeCollection``."""

        return self.build(
            user_requirement=user_requirement,
            business_rules=knowledge.get_section(KnowledgeSection.BUSINESS),
            database_knowledge=knowledge.get_section(KnowledgeSection.DATABASE),
            thinking_layer=knowledge.get_section(KnowledgeSection.THINKING),
            requirement_engine_knowledge=knowledge.get_section(
                KnowledgeSection.REQUIREMENT_ENGINE
            ),
        )


def _render_knowledge_items(items: Sequence[KnowledgeDocument | str]) -> str:
    """Render knowledge documents or raw strings into a markdown block."""

    if not items:
        return "No knowledge provided."

    rendered_items: list[str] = []
    for item in items:
        if isinstance(item, KnowledgeDocument):
            rendered_items.append(_render_document(item))
        else:
            content = str(item).strip()
            if content:
                rendered_items.append(content)

    return "\n\n".join(rendered_items) if rendered_items else "No knowledge provided."


def _render_document(document: KnowledgeDocument) -> str:
    """Render one knowledge document with source metadata."""

    if document.error:
        return (
            f"### {document.relative_path}\n\n"
            f"Document could not be loaded.\n\nError: {document.error}"
        )

    content = document.content.strip() or "[Blank document]"
    return f"### {document.relative_path}\n\n{content}"
