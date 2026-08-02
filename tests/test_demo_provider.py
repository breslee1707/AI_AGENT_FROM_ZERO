from __future__ import annotations

import unittest
from pathlib import Path

from agent_core.agent import Agent
from agent_core.mcp_client import MCPToolProvider
from agent_core.providers import DemoClient
from agent_core.tools import build_default_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DemoProviderTests(unittest.TestCase):
    def test_runs_full_agent_to_mcp_flow_without_api_key(self) -> None:
        provider = MCPToolProvider.from_config(PROJECT_ROOT / "mcp_servers.json")
        try:
            registry = build_default_registry(provider.specs())
            agent = Agent(DemoClient(), registry)

            result = agent.run("Tìm file trùng trong mcp_servers/demo_assets")
        finally:
            provider.close()

        self.assertEqual(len(result.steps), 1)
        self.assertTrue(result.steps[0].tool.endswith("__find_duplicate_files"))
        self.assertIn("config-backup.json", result.text)
        self.assertIn("MCP discovery và tool call vẫn chạy thật", result.text)

    def test_confirmation_selects_recoverable_trash_tool(self) -> None:
        provider = MCPToolProvider.from_config(PROJECT_ROOT / "mcp_servers.json")
        try:
            reply = DemoClient().complete(
                "",
                [
                    {
                        "role": "user",
                        "content": (
                            "Xác nhận dọn file trùng trong "
                            "mcp_servers/demo_assets"
                        ),
                    }
                ],
                provider.specs(),
            )
        finally:
            provider.close()

        self.assertEqual(len(reply.tool_calls), 1)
        call = reply.tool_calls[0]
        self.assertTrue(call["name"].endswith("__trash_duplicate_files"))
        self.assertEqual(call["args"]["confirmation"], "MOVE_DUPLICATES_TO_TRASH")


if __name__ == "__main__":
    unittest.main()
