"""Read-only MCP tools for inspecting files inside one configured workspace."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from typing import TypedDict

from mcp.server import MCPServer

WORKSPACE_ROOT = Path(os.getenv("MCP_WORKSPACE_ROOT", ".")).resolve()
mcp = MCPServer(
    "workspace-tools",
    instructions="Read-only tools for inspecting files inside one workspace.",
)


class DuplicateGroup(TypedDict):
    hash: str
    files: list[str]
    size_bytes: int
    reclaimable_bytes: int


class DuplicateReport(TypedDict):
    groups: list[DuplicateGroup]
    total_groups: int
    total_reclaimable_bytes: int


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@mcp.tool()
def find_duplicate_files(
    subfolder: str = "mcp_servers/demo_assets",
    min_size_kb: int = 0,
) -> DuplicateReport:
    """Find files with identical content inside a workspace subfolder."""
    if min_size_kb < 0:
        raise ValueError("min_size_kb must be zero or greater")

    target = (WORKSPACE_ROOT / subfolder).resolve()
    if not target.is_relative_to(WORKSPACE_ROOT):
        raise ValueError("subfolder must stay inside the configured workspace")
    if not target.is_dir():
        raise ValueError(f"folder does not exist: {subfolder}")

    minimum_bytes = min_size_kb * 1024
    by_hash: dict[str, list[Path]] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.stat().st_size >= minimum_bytes:
            by_hash.setdefault(_hash_file(path), []).append(path)

    groups: list[DuplicateGroup] = []
    for digest, paths in sorted(by_hash.items()):
        if len(paths) < 2:
            continue
        size_bytes = paths[0].stat().st_size
        groups.append(
            {
                "hash": f"{digest[:12]}...",
                "files": [
                    path.relative_to(WORKSPACE_ROOT).as_posix() for path in paths
                ],
                "size_bytes": size_bytes,
                "reclaimable_bytes": size_bytes * (len(paths) - 1),
            }
        )

    return {
        "groups": groups,
        "total_groups": len(groups),
        "total_reclaimable_bytes": sum(group["reclaimable_bytes"] for group in groups),
    }


if __name__ == "__main__":
    mcp.run()
