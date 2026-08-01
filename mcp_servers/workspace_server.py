"""MCP tools for finding and safely trashing duplicates inside one workspace."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from typing import TypedDict

from mcp.server import MCPServer
from send2trash import send2trash

WORKSPACE_ROOT = Path(os.getenv("MCP_WORKSPACE_ROOT", ".")).resolve()
mcp = MCPServer(
    "workspace-tools",
    instructions=(
        "Find duplicate files and move confirmed duplicate copies to the OS trash. "
        "Every path stays inside one configured workspace."
    ),
)

CONFIRM_TRASH = "MOVE_DUPLICATES_TO_TRASH"


class DuplicateGroup(TypedDict):
    hash: str
    files: list[str]
    size_bytes: int
    reclaimable_bytes: int


class DuplicateReport(TypedDict):
    groups: list[DuplicateGroup]
    total_groups: int
    total_reclaimable_bytes: int


class TrashReport(TypedDict):
    kept_files: list[str]
    moved_files: list[str]
    moved_bytes: int
    recoverable: bool


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_subfolder(subfolder: str) -> Path:
    target = (WORKSPACE_ROOT / subfolder).resolve()
    if not target.is_relative_to(WORKSPACE_ROOT):
        raise ValueError("subfolder must stay inside the configured workspace")
    if not target.is_dir():
        raise ValueError(f"folder does not exist: {subfolder}")
    return target


def _duplicate_paths(target: Path, minimum_bytes: int) -> list[list[Path]]:
    by_hash: dict[str, list[Path]] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.stat().st_size >= minimum_bytes:
            by_hash.setdefault(_hash_file(path), []).append(path)
    return [paths for _, paths in sorted(by_hash.items()) if len(paths) >= 2]


@mcp.tool()
def find_duplicate_files(
    subfolder: str = "mcp_servers/demo_assets",
    min_size_kb: int = 0,
) -> DuplicateReport:
    """Find files with identical content inside a workspace subfolder."""
    if min_size_kb < 0:
        raise ValueError("min_size_kb must be zero or greater")

    target = _resolve_subfolder(subfolder)

    minimum_bytes = min_size_kb * 1024
    groups: list[DuplicateGroup] = []
    for paths in _duplicate_paths(target, minimum_bytes):
        size_bytes = paths[0].stat().st_size
        groups.append(
            {
                "hash": f"{_hash_file(paths[0])[:12]}...",
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


@mcp.tool()
def trash_duplicate_files(
    subfolder: str = "mcp_servers/demo_assets",
    confirmation: str = "",
) -> TrashReport:
    """Move duplicate copies to the OS trash after explicit confirmation.

    The first file in each sorted duplicate group is kept. Pass the exact confirmation
    value ``MOVE_DUPLICATES_TO_TRASH`` only after the user approves the preview.
    """
    if confirmation != CONFIRM_TRASH:
        raise ValueError(
            "explicit confirmation required: preview first, then pass "
            f"confirmation='{CONFIRM_TRASH}'"
        )

    target = _resolve_subfolder(subfolder)
    kept_files: list[str] = []
    moved_files: list[str] = []
    moved_bytes = 0

    for paths in _duplicate_paths(target, minimum_bytes=0):
        kept_files.append(paths[0].relative_to(WORKSPACE_ROOT).as_posix())
        for path in paths[1:]:
            moved_bytes += path.stat().st_size
            moved_files.append(path.relative_to(WORKSPACE_ROOT).as_posix())
            send2trash(str(path))

    return {
        "kept_files": kept_files,
        "moved_files": moved_files,
        "moved_bytes": moved_bytes,
        "recoverable": True,
    }


if __name__ == "__main__":
    mcp.run()
