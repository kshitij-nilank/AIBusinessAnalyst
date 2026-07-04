"""Knowledge loading utilities for the requirement engine.

The loader is responsible for reading and organizing project knowledge from
markdown files. It does not perform AI reasoning, business interpretation,
prompt construction, retrieval ranking, or SQL generation.

The default implementation loads markdown files from the local repository, but
the ``KnowledgeStore`` protocol is intentionally small so future vector
databases or external knowledge stores can provide the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol


class KnowledgeSection(str, Enum):
    """Known knowledge areas used by the AI Business Analyst project."""

    BUSINESS = "business"
    DATABASE = "database"
    REQUIREMENT_ENGINE = "requirement_engine"
    THINKING = "thinking"


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A loaded markdown knowledge document.

    Attributes:
        section: Logical knowledge area the file belongs to.
        path: Absolute filesystem path to the source file.
        relative_path: Project-relative path for display and references.
        name: File name, including extension.
        stem: File name without extension.
        content: Raw markdown content.
        exists: Whether the file existed and was successfully read.
        error: Read error message, if loading failed.
    """

    section: KnowledgeSection
    path: Path
    relative_path: str
    name: str
    stem: str
    content: str
    exists: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, str | bool | None]:
        """Return a JSON-serializable dictionary representation."""

        return {
            "section": self.section.value,
            "path": str(self.path),
            "relative_path": self.relative_path,
            "name": self.name,
            "stem": self.stem,
            "content": self.content,
            "exists": self.exists,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeCollection:
    """A structured collection of loaded knowledge documents.

    Attributes:
        project_root: Absolute project root used for loading.
        documents_by_section: Loaded markdown documents grouped by section.
        missing_paths: Expected directories that were not found.
        errors: Non-fatal loading errors.
    """

    project_root: Path
    documents_by_section: dict[KnowledgeSection, list[KnowledgeDocument]]
    missing_paths: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def documents(self) -> list[KnowledgeDocument]:
        """Return all loaded documents as a flat list."""

        return [
            document
            for documents in self.documents_by_section.values()
            for document in documents
        ]

    def get_section(self, section: KnowledgeSection) -> list[KnowledgeDocument]:
        """Return documents for a single knowledge section."""

        return list(self.documents_by_section.get(section, []))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary representation."""

        return {
            "project_root": str(self.project_root),
            "documents_by_section": {
                section.value: [document.to_dict() for document in documents]
                for section, documents in self.documents_by_section.items()
            },
            "missing_paths": [str(path) for path in self.missing_paths],
            "errors": list(self.errors),
        }


class KnowledgeStore(Protocol):
    """Protocol for local or external knowledge stores.

    Future stores, such as vector databases, document APIs, or remote object
    stores, should implement this protocol and return a ``KnowledgeCollection``.
    """

    def load(self, force_reload: bool = False) -> KnowledgeCollection:
        """Load and return a structured knowledge collection."""


class FileSystemKnowledgeStore:
    """Local markdown-backed knowledge store.

    The store reads markdown files from:
    - ``knowledge/business``
    - ``knowledge/database``
    - ``knowledge/requirement_engine``
    - ``thinking``

    Loaded collections are cached in memory. Use ``force_reload=True`` to
    refresh the cache after files change.
    """

    DEFAULT_SECTION_PATHS: dict[KnowledgeSection, str] = {
        KnowledgeSection.BUSINESS: "knowledge/business",
        KnowledgeSection.DATABASE: "knowledge/database",
        KnowledgeSection.REQUIREMENT_ENGINE: "knowledge/requirement_engine",
        KnowledgeSection.THINKING: "thinking",
    }

    def __init__(
        self,
        project_root: Path | str | None = None,
        section_paths: dict[KnowledgeSection, str] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Create a filesystem knowledge store.

        Args:
            project_root: Root of the ``AIBusinessAnalyst`` project. If omitted,
                it is inferred from this module's location.
            section_paths: Optional section-to-folder mapping for custom layouts.
            encoding: Text encoding used when reading markdown files.
        """

        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.section_paths = section_paths or self.DEFAULT_SECTION_PATHS
        self.encoding = encoding
        self._cache: KnowledgeCollection | None = None

    def load(self, force_reload: bool = False) -> KnowledgeCollection:
        """Load all configured markdown knowledge files.

        Missing directories and unreadable files are recorded as non-fatal
        errors. The method returns an empty section list for missing directories
        instead of raising.
        """

        if self._cache is not None and not force_reload:
            return self._cache

        documents_by_section: dict[KnowledgeSection, list[KnowledgeDocument]] = {
            section: [] for section in self.section_paths
        }
        missing_paths: list[Path] = []
        errors: list[str] = []

        for section, relative_folder in self.section_paths.items():
            folder = self.project_root / relative_folder
            if not folder.exists():
                missing_paths.append(folder)
                errors.append(f"Missing knowledge folder: {folder}")
                continue

            if not folder.is_dir():
                errors.append(f"Knowledge path is not a directory: {folder}")
                continue

            for path in sorted(folder.rglob("*.md")):
                document = self._load_markdown_file(section, path)
                documents_by_section[section].append(document)
                if document.error:
                    errors.append(document.error)

        self._cache = KnowledgeCollection(
            project_root=self.project_root,
            documents_by_section=documents_by_section,
            missing_paths=missing_paths,
            errors=errors,
        )
        return self._cache

    def get_document(
        self,
        relative_path: str,
        section: KnowledgeSection | None = None,
        force_reload: bool = False,
    ) -> KnowledgeDocument | None:
        """Return one loaded document by project-relative path.

        Args:
            relative_path: Project-relative path, such as
                ``knowledge/business/BR-001_FYear.md``.
            section: Optional section filter.
            force_reload: Whether to refresh the cache before lookup.
        """

        collection = self.load(force_reload=force_reload)
        sections = [section] if section is not None else list(collection.documents_by_section)

        normalized = relative_path.replace("\\", "/")
        for current_section in sections:
            for document in collection.get_section(current_section):
                if document.relative_path.replace("\\", "/") == normalized:
                    return document
        return None

    def clear_cache(self) -> None:
        """Clear the in-memory loaded knowledge cache."""

        self._cache = None

    def _load_markdown_file(
        self,
        section: KnowledgeSection,
        path: Path,
    ) -> KnowledgeDocument:
        """Read one markdown file into a ``KnowledgeDocument``."""

        relative_path = self._relative_path(path)
        try:
            content = path.read_text(encoding=self.encoding)
        except OSError as exc:
            return KnowledgeDocument(
                section=section,
                path=path,
                relative_path=relative_path,
                name=path.name,
                stem=path.stem,
                content="",
                exists=path.exists(),
                error=f"Failed to read {path}: {exc}",
            )
        except UnicodeDecodeError as exc:
            return KnowledgeDocument(
                section=section,
                path=path,
                relative_path=relative_path,
                name=path.name,
                stem=path.stem,
                content="",
                exists=True,
                error=f"Failed to decode {path}: {exc}",
            )

        return KnowledgeDocument(
            section=section,
            path=path,
            relative_path=relative_path,
            name=path.name,
            stem=path.stem,
            content=content,
        )

    def _relative_path(self, path: Path) -> str:
        """Return a stable project-relative path when possible."""

        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return path.as_posix()


class KnowledgeLoader:
    """Facade for loading organized project knowledge.

    This class keeps callers decoupled from the concrete storage mechanism. By
    default it uses ``FileSystemKnowledgeStore``. A future vector database or
    external knowledge service can be injected as long as it implements the
    ``KnowledgeStore`` protocol.
    """

    def __init__(self, store: KnowledgeStore | None = None) -> None:
        """Create a loader with an optional custom knowledge store."""

        self.store = store or FileSystemKnowledgeStore()

    def load(self, force_reload: bool = False) -> KnowledgeCollection:
        """Load and return structured knowledge without reasoning over it."""

        return self.store.load(force_reload=force_reload)
