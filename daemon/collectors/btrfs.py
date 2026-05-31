"""
Universal System Monitor — BTRFS Snapshot Collector

Auto-detects BTRFS filesystems and lists snapshots via snapper or btrfs
subvolume list. Provides filesystem usage info.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess

logger = logging.getLogger("usm.collectors.btrfs")


class BtrfsCollector:
    """Collects BTRFS snapshot and filesystem data."""

    channel = "snapshots"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.btrfs
        self._snapper = shutil.which("snapper")
        self._btrfs = shutil.which("btrfs")
        self._is_btrfs = self._detect_btrfs()

    def _detect_btrfs(self) -> bool:
        """Check if root filesystem is BTRFS."""
        try:
            result = subprocess.run(
                ["findmnt", "-t", "btrfs", "-J"],
                capture_output=True, text=True, timeout=5,
            )
            data = json.loads(result.stdout) if result.stdout.strip() else {}
            fs_list = data.get("filesystems", [])
            return len(fs_list) > 0
        except Exception:
            return False

    async def run(self):
        """Main collector loop."""
        if not self._is_btrfs:
            logger.info("No BTRFS filesystem detected, snapshot collector disabled")
            # Send disabled status once
            await self.ws_manager.broadcast(self.channel, {"available": False})
            return

        logger.info("BTRFS detected, snapshot collector active")

        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("BTRFS collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect BTRFS data."""
        snapshots = self._get_snapshots()
        subvolumes = self._get_subvolumes()
        usage = self._get_usage()

        return {
            "available": True,
            "snapshots": snapshots,
            "subvolumes": subvolumes,
            "usage": usage,
            "has_snapper": bool(self._snapper),
            "summary": {
                "snapshot_count": len(snapshots),
                "subvolume_count": len(subvolumes),
            },
        }

    def _get_snapshots(self) -> list[dict]:
        """Get snapshots via snapper or btrfs subvolume list."""
        if self._snapper:
            return self._get_snapper_snapshots()
        return self._get_btrfs_snapshots()

    def _get_snapper_snapshots(self) -> list[dict]:
        """Get snapshots via snapper."""
        try:
            result = subprocess.run(
                [self._snapper, "list", "--columns", "number,type,date,description,cleanup"],
                capture_output=True, text=True, timeout=10,
            )
            snapshots = []
            lines = result.stdout.strip().split("\n")
            for line in lines[2:]:  # Skip header lines
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    try:
                        snapshots.append({
                            "number": int(parts[0]),
                            "type": parts[1],
                            "date": parts[2],
                            "description": parts[3],
                            "cleanup": parts[4],
                        })
                    except (ValueError, IndexError):
                        continue
            return snapshots
        except Exception as e:
            logger.debug("snapper list failed: %s", e)
            return []

    def _get_btrfs_snapshots(self) -> list[dict]:
        """Get subvolumes that look like snapshots via btrfs subvolume list."""
        try:
            result = subprocess.run(
                [self._btrfs, "subvolume", "list", "-s", "/"],
                capture_output=True, text=True, timeout=10,
            )
            snapshots = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # Format: ID xxx gen xxx top level xxx path <path>
                parts = line.split()
                path_idx = line.find("path ")
                if path_idx >= 0:
                    path = line[path_idx + 5:]
                    snapshots.append({
                        "path": path,
                        "id": int(parts[1]) if len(parts) > 1 else 0,
                    })
            return snapshots
        except Exception:
            return []

    def _get_subvolumes(self) -> list[dict]:
        """List all subvolumes."""
        if not self._btrfs:
            return []
        try:
            result = subprocess.run(
                [self._btrfs, "subvolume", "list", "/"],
                capture_output=True, text=True, timeout=10,
            )
            subvols = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                path_idx = line.find("path ")
                if path_idx >= 0:
                    subvols.append({
                        "id": int(parts[1]) if len(parts) > 1 else 0,
                        "path": line[path_idx + 5:],
                    })
            return subvols
        except Exception:
            return []

    def _get_usage(self) -> dict:
        """Get BTRFS filesystem usage."""
        if not self._btrfs:
            return {}
        try:
            result = subprocess.run(
                [self._btrfs, "filesystem", "usage", "/", "--raw"],
                capture_output=True, text=True, timeout=10,
            )
            return {"raw": result.stdout[:1000]}
        except Exception:
            return {}
