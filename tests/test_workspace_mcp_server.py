from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp import Client

from mcp_servers.workspace_server import CONFIRM_TRASH, mcp


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

    async def test_trash_requires_confirmation(self) -> None:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "trash_duplicate_files",
                {"subfolder": "mcp_servers/demo_assets", "confirmation": ""},
            )

        self.assertTrue(result.is_error)

    async def test_keeps_one_copy_and_moves_the_rest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            demo = root / "demo"
            trash = root / "trash"
            demo.mkdir()
            trash.mkdir()
            (demo / "config-backup.json").write_text("same", encoding="utf-8")
            (demo / "config.json").write_text("same", encoding="utf-8")
            (demo / "notes.txt").write_text("different", encoding="utf-8")

            def fake_send2trash(raw_path: str) -> None:
                path = Path(raw_path)
                path.replace(trash / path.name)

            with (
                patch("mcp_servers.workspace_server.WORKSPACE_ROOT", root),
                patch(
                    "mcp_servers.workspace_server.send2trash",
                    side_effect=fake_send2trash,
                ),
            ):
                async with Client(mcp, raise_exceptions=True) as client:
                    result = await client.call_tool(
                        "trash_duplicate_files",
                        {"subfolder": "demo", "confirmation": CONFIRM_TRASH},
                    )

            self.assertFalse(result.is_error)
            self.assertIsNotNone(result.structured_content)
            self.assertEqual(
                result.structured_content["moved_files"],
                ["demo/config.json"],
            )
            self.assertTrue((demo / "config-backup.json").is_file())
            self.assertTrue((trash / "config.json").is_file())


if __name__ == "__main__":
    unittest.main()
