"""
Universal System Monitor — CachyOS Scheduler Collector

Detects the active CPU scheduler (BORE, sched-ext, EEVDF, CFS),
reads per-CPU scheduling stats from /proc/schedstat, and reports
CachyOS kernel variant info.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import time
from pathlib import Path

logger = logging.getLogger("usm.collectors.scheduler")


class SchedulerCollector:
    """Collects CPU scheduler and CachyOS kernel info."""

    channel = "scheduler"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.scheduler
        self._prev_schedstat: dict[int, tuple[float, int, int, int]] = {}

    async def run(self):
        """Main collector loop."""
        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect scheduler data."""
        now = time.time()
        kernel = platform.release()
        scheduler = self._detect_scheduler()
        sched_ext_info = self._get_sched_ext_info()
        per_cpu = self._get_schedstat(now)
        features = self._get_sched_features()

        # CachyOS variant
        variant = ""
        if "-cachyos" in kernel:
            variant = "CachyOS"
            if "-bore" in kernel:
                variant += " BORE"
            elif "-eevdf" in kernel:
                variant += " EEVDF"
            elif "-sched-ext" in kernel or "-scx" in kernel:
                variant += " sched-ext"
            elif "-rt" in kernel:
                variant += " RT"
            elif "-hardened" in kernel:
                variant += " Hardened"

        return {
            "kernel": kernel,
            "variant": variant,
            "scheduler": scheduler,
            "sched_ext": sched_ext_info,
            "per_cpu": per_cpu,
            "features": features,
        }

    def _detect_scheduler(self) -> str:
        """Detect the active CPU scheduler."""
        # Check sched-ext first
        sched_ext_ops = Path("/sys/kernel/sched_ext/root/ops")
        if sched_ext_ops.exists():
            try:
                ops = sched_ext_ops.read_text().strip()
                if ops:
                    return f"sched-ext ({ops})"
            except OSError:
                pass

        # Check for BORE
        bore_path = Path("/proc/sys/kernel/sched_bore")
        if bore_path.exists():
            return "BORE"

        # Check sched_debug for hints
        try:
            with open("/proc/sched_debug") as f:
                first_lines = f.read(500)
                if "EEVDF" in first_lines:
                    return "EEVDF"
                if "CFS" in first_lines:
                    return "CFS"
        except (OSError, PermissionError):
            pass

        # Check kernel config
        try:
            with open(f"/boot/config-{platform.release()}") as f:
                for line in f:
                    if "CONFIG_SCHED_BORE" in line and "=y" in line:
                        return "BORE"
        except OSError:
            pass

        return "CFS (default)"

    def _get_sched_ext_info(self) -> dict:
        """Get sched-ext details if active."""
        base = Path("/sys/kernel/sched_ext")
        if not base.exists():
            return {"available": False}

        info = {"available": True}

        root = base / "root"
        if root.exists():
            ops_file = root / "ops"
            if ops_file.exists():
                try:
                    info["ops"] = ops_file.read_text().strip()
                except OSError:
                    pass

            enabled_file = root / "enable"
            if enabled_file.exists():
                try:
                    info["enabled"] = enabled_file.read_text().strip() == "1"
                except OSError:
                    pass

        return info

    def _get_schedstat(self, now: float) -> list[dict]:
        """Parse /proc/schedstat for per-CPU stats."""
        try:
            with open("/proc/schedstat") as f:
                content = f.read()
        except (OSError, PermissionError):
            return []

        cpus = []
        for line in content.split("\n"):
            if not line.startswith("cpu"):
                continue
            parts = line.split()
            if len(parts) < 10:
                continue

            cpu_match = re.match(r"cpu(\d+)", parts[0])
            if not cpu_match:
                continue

            cpu_id = int(cpu_match.group(1))
            # schedstat fields: yld_count, sched_count, sched_goidle,
            # ttwu_count, ttwu_local, rq_cpu_time, rq_sched_info.run_delay, rq_sched_info.pcount
            running_ns = int(parts[7]) if len(parts) > 7 else 0
            waiting_ns = int(parts[8]) if len(parts) > 8 else 0
            timeslices = int(parts[9]) if len(parts) > 9 else 0

            # Calculate rates
            ctx_switches_s = 0
            if cpu_id in self._prev_schedstat:
                prev_time, prev_run, prev_wait, prev_ts = self._prev_schedstat[cpu_id]
                dt = now - prev_time
                if dt > 0:
                    ctx_switches_s = (timeslices - prev_ts) / dt

            self._prev_schedstat[cpu_id] = (now, running_ns, waiting_ns, timeslices)

            cpus.append({
                "cpu": cpu_id,
                "running_ns": running_ns,
                "waiting_ns": waiting_ns,
                "timeslices": timeslices,
                "context_switches_s": round(ctx_switches_s, 1),
            })

        return cpus

    def _get_sched_features(self) -> list[str]:
        """Get scheduler features from debugfs."""
        try:
            with open("/sys/kernel/debug/sched/features") as f:
                content = f.read().strip()
            features = []
            for feat in content.split():
                features.append(feat)
            return features
        except (OSError, PermissionError):
            return []
