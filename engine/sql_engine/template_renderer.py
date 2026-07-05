"""Jinja2 SQL template rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


class SQLTemplateRenderer:
    """Load and render SQL templates from the SQL engine template directory."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """Create a renderer for SQL templates."""

        self.template_dir = template_dir or Path(__file__).resolve().parent / "templates"
        self.environment = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a SQL template with the provided context."""

        template = self.environment.get_template(template_name)
        return template.render(**context).strip()

