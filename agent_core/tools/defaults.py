"""Composition root for the tools enabled by default."""

from __future__ import annotations

from .calculator import CALCULATOR_TOOL
from .currency import CURRENCY_TOOL
from .pdf_reader import PDF_READER_TOOL
from .registry import ToolRegistry


DEFAULT_TOOLS = (
    PDF_READER_TOOL,
    CALCULATOR_TOOL,
    CURRENCY_TOOL,
)


def build_default_registry() -> ToolRegistry:
    """Build a registry containing the project's default tool set."""
    return ToolRegistry(list(DEFAULT_TOOLS))
