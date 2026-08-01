"""Discover and call the demo MCP tool without an LLM or API key."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_core.mcp_client import MCPToolProvider


def main() -> None:
    config_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "mcp_servers.json"
    )
    provider = MCPToolProvider.from_config(config_path)
    try:
        specs = provider.specs()
        print("MCP tools đã khám phá qua tools/list:")
        for spec in specs:
            print(f"- {spec.name}")
            print(f"  {spec.description}")

        duplicate_tool = next(
            spec for spec in specs if spec.name.endswith("__find_duplicate_files")
        )
        print(f"\nGọi {duplicate_tool.name} qua tools/call...")
        print(duplicate_tool.func(subfolder="mcp_servers/demo_assets", min_size_kb=0))
    finally:
        provider.close()


if __name__ == "__main__":
    main()
