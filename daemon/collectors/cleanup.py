"""
Universal System Monitor — Cleanup Collector

Scans for system junk: package cache, temp files, old logs,
thumbnail cache, trash, and orphan packages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("usm.collectors.cleanup")


def _dir_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file() and not entry.is_symlink():
                    total += entry.stat().st_size
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass
    return total


def _file_count(path: Path) -> int:
    """Count files in directory."""
    try:
        return sum(1 for f in path.rglob("*") if f.is_file())
    except (OSError, PermissionError):
        return 0


class CleanupCollector:
    """Scans for reclaimable disk space."""

    channel = "cleanup"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = 120  # Scan every 2 minutes (not too frequent)

    async def run(self):
        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Cleanup collector error")
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        home = Path.home()
        categories = []
        total_size = 0

        # 1. Package manager cache
        pkg_caches = [
            ("/var/cache/pacman/pkg", "Pacman Cache", "pacman"),
            (str(home / ".cache" / "yay"), "AUR Cache (yay)", "yay"),
            (str(home / ".cache" / "paru"), "AUR Cache (paru)", "paru"),
            ("/var/cache/apt/archives", "APT Cache", "apt"),
            ("/var/cache/dnf", "DNF Cache", "dnf"),
        ]
        for path_str, label, mgr in pkg_caches:
            p = Path(path_str)
            if p.exists():
                size = _dir_size(p)
                if size > 0:
                    categories.append({
                        "id": f"pkg_{mgr}",
                        "name": label,
                        "icon": "📦",
                        "path": path_str,
                        "size": size,
                        "files": _file_count(p),
                        "safe": True,
                        "action": f"clean_{mgr}",
                    })
                    total_size += size

        # 2. User cache (~/.cache)
        cache_dir = home / ".cache"
        if cache_dir.exists():
            size = _dir_size(cache_dir)
            if size > 1_000_000:  # Only show if > 1MB
                categories.append({
                    "id": "user_cache",
                    "name": "User Cache (~/.cache)",
                    "icon": "🗂️",
                    "path": str(cache_dir),
                    "size": size,
                    "files": _file_count(cache_dir),
                    "safe": True,
                    "action": "clean_user_cache",
                })
                total_size += size

        # 3. Thumbnails
        thumb_dir = home / ".cache" / "thumbnails"
        if thumb_dir.exists():
            size = _dir_size(thumb_dir)
            if size > 100_000:
                categories.append({
                    "id": "thumbnails",
                    "name": "Thumbnail Cache",
                    "icon": "🖼️",
                    "path": str(thumb_dir),
                    "size": size,
                    "files": _file_count(thumb_dir),
                    "safe": True,
                    "action": "clean_thumbnails",
                })
                # Don't add to total — already counted in user_cache

        # 4. Trash
        trash_dir = home / ".local" / "share" / "Trash"
        if trash_dir.exists():
            size = _dir_size(trash_dir)
            if size > 0:
                categories.append({
                    "id": "trash",
                    "name": "Trash",
                    "icon": "🗑️",
                    "path": str(trash_dir),
                    "size": size,
                    "files": _file_count(trash_dir / "files") if (trash_dir / "files").exists() else 0,
                    "safe": True,
                    "action": "clean_trash",
                })
                total_size += size

        # 5. Old journal logs
        try:
            result = subprocess.run(
                ["journalctl", "--disk-usage"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # "Archived and active journals take up 256.0M in the file system."
                line = result.stdout.strip()
                import re
                match = re.search(r'([\d.]+)\s*([KMGT])', line)
                if match:
                    val = float(match.group(1))
                    unit = match.group(2)
                    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
                    size = int(val * multipliers.get(unit, 1))
                    if size > 50_000_000:  # Only show if > 50MB
                        categories.append({
                            "id": "journal",
                            "name": "System Journal Logs",
                            "icon": "📋",
                            "path": "/var/log/journal",
                            "size": size,
                            "files": 0,
                            "safe": True,
                            "action": "clean_journal",
                        })
                        total_size += size
        except Exception:
            pass

        # 6. /tmp
        tmp_dir = Path("/tmp")
        if tmp_dir.exists():
            size = _dir_size(tmp_dir)
            if size > 10_000_000:  # > 10MB
                categories.append({
                    "id": "tmp",
                    "name": "Temp Files (/tmp)",
                    "icon": "🔥",
                    "path": "/tmp",
                    "size": size,
                    "files": _file_count(tmp_dir),
                    "safe": False,  # Some programs use /tmp actively
                    "action": "clean_tmp",
                })
                total_size += size

        # 7. Old coredumps
        coredump_dir = Path("/var/lib/systemd/coredump")
        if coredump_dir.exists():
            size = _dir_size(coredump_dir)
            if size > 0:
                categories.append({
                    "id": "coredumps",
                    "name": "Core Dumps",
                    "icon": "💥",
                    "path": str(coredump_dir),
                    "size": size,
                    "files": _file_count(coredump_dir),
                    "safe": True,
                    "action": "clean_coredumps",
                })
                total_size += size

        # 8. Orphan packages (Arch only)
        orphans = []
        try:
            result = subprocess.run(
                ["pacman", "-Qdtq"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                orphans = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        except Exception:
            pass

        # Sort by size descending
        categories.sort(key=lambda c: c["size"], reverse=True)

        return {
            "categories": categories,
            "total_size": total_size,
            "orphan_packages": orphans,
            "orphan_count": len(orphans),
        }
