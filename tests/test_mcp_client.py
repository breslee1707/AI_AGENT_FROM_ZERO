from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from agent_core.mcp_client import (
    MCPServerConfig,
    MCPToolProvider,
    load_mcp_server_configs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MCPToolProviderTests(unittest.TestCase):
    def test_loads_portable_python_and_relative_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "mcp.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "demo": {
                                "command": "${PYTHON}",
                                "args": ["server.py"],
                                "cwd": ".",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            [config] = load_mcp_server_configs(config_path)

        self.assertEqual(config.command, sys.executable)
        self.assertEqual(config.cwd, root.resolve())

    def test_discovers_and_calls_stdio_tool(self) -> None:
        provider = MCPToolProvider(
            [
                MCPServerConfig(
                    name="workspace-tools",
                    command=sys.executable,
                    args=("mcp_servers/workspace_server.py",),
                    cwd=PROJECT_ROOT,
                    env={"MCP_WORKSPACE_ROOT": "."},
                )
            ]
        )
        try:
            specs = provider.specs()
            tool = next(
                spec for spec in specs if spec.name.endswith("__find_duplicate_files")
            )
            result = tool.func(
                subfolder="mcp_servers/demo_assets",
                min_size_kb=0,
            )
        finally:
            provider.close()

        self.assertIn('"total_groups": 1', result)
        self.assertIn("config-backup.json", result)


if __name__ == "__main__":
    unittest.main()
