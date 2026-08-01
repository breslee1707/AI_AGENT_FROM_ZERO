"""Composition root for the tools enabled by default."""

from __future__ import annotations

from collections.abc import Iterable

from .base import ToolSpec
from .calculator import CALCULATOR_TOOL
from .currency import CURRENCY_TOOL
from .pdf_reader import PDF_READER_TOOL
from .registry import ToolRegistry


DEFAULT_TOOLS = (
    PDF_READER_TOOL,
    CALCULATOR_TOOL,
    CURRENCY_TOOL,
)


def build_default_registry(extra_tools: Iterable[ToolSpec] = ()) -> ToolRegistry:
    """Build a registry containing local tools plus optional external tools."""
    return ToolRegistry([*DEFAULT_TOOLS, *extra_tools])
