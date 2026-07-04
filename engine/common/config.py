"""Application configuration helpers."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_environment(env_file: str | Path = ".env", override: bool = True) -> bool:
    """Load environment variables from a dotenv file.

    Returns ``True`` when a dotenv file is found and loaded, otherwise
    ``False``.
    """

    return load_dotenv(dotenv_path=env_file, override=override)
