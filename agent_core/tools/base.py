"""Shared type definitions for agent tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ToolSpec:
    """Provider-neutral description of a callable tool.

    Each provider adapter translates this definition to its own function-calling
    format. Tool implementations therefore remain independent from LLM SDKs.
    """

    name: str
    description: str
    parameters: dict
    func: Callable[..., str]
