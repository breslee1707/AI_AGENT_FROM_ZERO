"""Public tool API.

Imports from ``agent_core.tools`` remain stable while implementations live in small,
focused modules that can be maintained and tested independently.
"""

from .base import ToolSpec
from .calculator import CALCULATOR_TOOL, calculator
from .currency import CURRENCY_TOOL, convert_currency
from .defaults import DEFAULT_TOOLS, build_default_registry
from .pdf_reader import PDF_READER_TOOL, read_pdf
from .registry import ToolRegistry

__all__ = [
    "CALCULATOR_TOOL",
    "CURRENCY_TOOL",
    "DEFAULT_TOOLS",
    "PDF_READER_TOOL",
    "ToolRegistry",
    "ToolSpec",
    "build_default_registry",
    "calculator",
    "convert_currency",
    "read_pdf",
]
