"""
Universal System Monitor — cgroups v2 Collector

Reads /sys/fs/cgroup/ hierarchy for precise resource tracking.
Maps Docker containers and systemd services to their cgroup slices.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("usm.collectors.cgroups")

CGROUP_BASE = Path("/sys/fs/cgroup")


class CgroupsCollector:
    """Collects cgroups v2 resource data."""

    channel = "cgroups"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.cgroups
        self._prev_cpu: dict[str, tuple[float, int]] = {}  # path -> (timestamp, usage_usec)

    async def run(self):
        """Main collector loop."""
        if not CGROUP_BASE.exists():
            logger.info("cgroups v2 not available, collector disabled")
            return

        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cgroups collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect cgroup data."""
        now = time.time()
        docker_cgroups = []
        service_cgroups = []

        # Docker containers: /sys/fs/cgroup/system.slice/docker-<id>.scope/
        docker_slice = CGROUP_BASE / "system.slice"
        if docker_slice.is_dir():
            for entry in docker_slice.iterdir():
                if entry.name.startswith("docker-") and entry.name.endswith(".scope"):
                    container_id = entry.name[7:-6][:12]
                    cg = self._read_cgroup(entry, now)
                    cg["container_id"] = container_id
                    docker_cgroups.append(cg)

        # systemd services: /sys/fs/cgroup/system.slice/<service>.service/
        if docker_slice.is_dir():
            for entry in docker_slice.iterdir():
                if entry.name.endswith(".service") and entry.is_dir():
                    cg = self._read_cgroup(entry, now)
                    cg["service"] = entry.name.replace(".service", "")
                    service_cgroups.append(cg)

        # Root cgroup
        root = self._read_cgroup(CGROUP_BASE, now)

        return {
            "root": root,
            "docker": docker_cgroups,
            "services": service_cgroups,
            "available_controllers": self._read_file(CGROUP_BASE / "cgroup.controllers"),
        }

    def _read_cgroup(self, path: Path, now: float) -> dict:
        """Read resource data from a cgroup directory."""
        data = {"path": str(path)}

        # CPU
        cpu_stat = self._parse_kv_file(path / "cpu.stat")
        usage_usec = int(cpu_stat.get("usage_usec", 0))
        data["cpu"] = {
            "usage_usec": usage_usec,
            "user_usec": int(cpu_stat.get("user_usec", 0)),
            "system_usec": int(cpu_stat.get("system_usec", 0)),
            "percent": self._calc_cpu_percent(str(path), now, usage_usec),
        }

        # Memory
        data["memory"] = {
            "current": self._read_int(path / "memory.current"),
            "max": self._read_int(path / "memory.max"),
            "swap": self._read_int(path / "memory.swap.current"),
        }
        if data["memory"]["max"] and data["memory"]["max"] < 2**62:
            data["memory"]["percent"] = round(
                data["memory"]["current"] / data["memory"]["max"] * 100, 1
            )
        else:
            data["memory"]["percent"] = 0

        # PIDs
        data["pids"] = {
            "current": self._read_int(path / "pids.current"),
            "max": self._read_file(path / "pids.max"),
        }

        # I/O
        io_stat = self._read_file(path / "io.stat")
        data["io"] = self._parse_io_stat(io_stat)

        return data

    def _calc_cpu_percent(self, path_key: str, now: float, usage_usec: int) -> float:
        """Calculate CPU% from usage_usec delta."""
        if path_key in self._prev_cpu:
            prev_time, prev_usage = self._prev_cpu[path_key]
            dt = now - prev_time
            if dt > 0:
                delta_usec = usage_usec - prev_usage
                # CPU% = (delta_usec / (dt * 1e6)) * 100
                cpu_percent = (delta_usec / (dt * 1_000_000)) * 100
                self._prev_cpu[path_key] = (now, usage_usec)
                return round(max(0, cpu_percent), 2)

        self._prev_cpu[path_key] = (now, usage_usec)
        return 0.0

    @staticmethod
    def _read_file(path: Path) -> str:
        """Read a sysfs file, returning empty string on error."""
        try:
            return path.read_text().strip()
        except (OSError, PermissionError):
            return ""

    @staticmethod
    def _read_int(path: Path) -> int:
        """Read an integer from a sysfs file."""
        try:
            val = path.read_text().strip()
            if val == "max":
                return 0
            return int(val)
        except (OSError, PermissionError, ValueError):
            return 0

    @staticmethod
    def _parse_kv_file(path: Path) -> dict[str, str]:
        """Parse a key-value sysfs file (space-separated)."""
        result = {}
        try:
            for line in path.read_text().strip().split("\n"):
                parts = line.split()
                if len(parts) >= 2:
                    result[parts[0]] = parts[1]
        except (OSError, PermissionError):
            pass
        return result

    @staticmethod
    def _parse_io_stat(content: str) -> dict:
        """Parse io.stat content."""
        total_read = 0
        total_write = 0
        for line in content.split("\n"):
            parts = line.split()
            for part in parts[1:]:
                if part.startswith("rbytes="):
                    total_read += int(part.split("=")[1])
                elif part.startswith("wbytes="):
                    total_write += int(part.split("=")[1])
        return {"read_bytes": total_read, "write_bytes": total_write}
