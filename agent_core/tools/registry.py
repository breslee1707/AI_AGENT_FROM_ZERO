"""Registration and safe execution of agent tools."""

from __future__ import annotations

from collections.abc import Iterable

from .base import ToolSpec


class ToolRegistry:
    """Store tool specifications and execute model-requested tool calls."""

    def __init__(self, specs: Iterable[ToolSpec]):
        specs = list(specs)
        names = [spec.name for spec in specs]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Trùng tên tool: {', '.join(duplicates)}")
        self._by_name = {spec.name: spec for spec in specs}

    def specs(self) -> list[ToolSpec]:
        """Return all tools currently exposed to the model."""
        return list(self._by_name.values())

    def run(self, name: str, args: dict) -> str:
        """Execute a tool and always return a model-readable string.

        Tool failures are observations for the agent, not fatal application errors.
        The model can inspect the error and decide how to recover on its next turn.
        """
        spec = self._by_name.get(name)
        if spec is None:
            return f"[Lỗi] Không có tool tên '{name}'."

        try:
            return spec.func(**args)
        except Exception as exc:  # noqa: BLE001 - isolate failures from tool code
            return f"[Lỗi khi chạy tool '{name}']: {exc}"
