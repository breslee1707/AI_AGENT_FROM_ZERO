from __future__ import annotations

import unittest

from mcp import Client

from mcp_servers.workspace_server import mcp


class WorkspaceMCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_and_calls_duplicate_finder(self) -> None:
        async with Client(mcp, raise_exceptions=True) as client:
            listed = await client.list_tools()
            names = [tool.name for tool in listed.tools]
            self.assertIn("find_duplicate_files", names)

            result = await client.call_tool(
                "find_duplicate_files",
                {"subfolder": "mcp_servers/demo_assets", "min_size_kb": 0},
            )

        self.assertFalse(result.is_error)
        self.assertIsNotNone(result.structured_content)
        self.assertEqual(result.structured_content["total_groups"], 1)

    async def test_rejects_path_outside_workspace(self) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "find_duplicate_files",
                {"subfolder": "../outside", "min_size_kb": 0},
            )

        self.assertTrue(result.is_error)


if __name__ == "__main__":
    unittest.main()
