"""Composition helpers shared by the Streamlit and CLI entry points."""

from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT, Settings
from .mcp_client import MCPToolProvider
from .tools import ToolRegistry, build_default_registry


def build_tool_registry(settings: Settings) -> ToolRegistry:
    """Combine built-in Python tools with tools discovered from MCP servers."""
    if not settings.mcp_config_path:
        return build_default_registry()

    config_path = Path(settings.mcp_config_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    provider = MCPToolProvider.from_config(
        config_path,
        timeout_seconds=settings.mcp_tool_timeout_seconds,
    )
    # Each generated ToolSpec closes over ``provider``, keeping the sessions alive.
    return build_default_registry(provider.specs())


__all__ = ["build_tool_registry"]
