"""
Universal System Monitor — Process Collector

Lists all running processes with per-process CPU, RAM, I/O, status.
Detects zombie processes and memory leaks (RSS climbing >50% over 1hr).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

import psutil

from daemon.actions.process_actions import get_process_safety

logger = logging.getLogger("usm.collectors.processes")


class ProcessCollector:
    """Collects per-process metrics and detects anomalies."""

    channel = "processes"

    def __init__(self, config, ws_manager, db=None, icon_resolver=None):
        self.config = config
        self.ws_manager = ws_manager
        self.db = db
        self.icon_resolver = icon_resolver
        self.interval = config.intervals.processes
        # Track RSS over time for leak detection: {pid: [(timestamp, rss), ...]}
        # Only sampled every 30s to save memory
        self._rss_history: dict[int, list[tuple[float, int]]] = defaultdict(list)
        self._leak_flagged: set[int] = set()
        self._leak_check_interval = 60
        self._last_leak_check = 0
        self._last_rss_sample = 0
        self._rss_sample_interval = 30  # Only sample RSS every 30s (not every 2s)
        self._max_process_list = 150  # Limit sent to frontend

    async def run(self):
        """Main collector loop."""
        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)

                # Store snapshots for leak detection
                if self.db:
                    await self.db.store_process_snapshots(data.get("processes", []))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Process collector error: %s", e)

            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect all process data (runs in thread pool)."""
        now = time.time()
        processes = []
        zombies = []
        total_count = 0
        running_count = 0
        sleeping_count = 0
        zombie_count = 0

        attrs = [
            "pid", "name", "username", "cpu_percent", "memory_percent",
            "memory_info", "status", "create_time", "cmdline", "nice",
            "num_threads", "ppid", "exe",
        ]

        for proc in psutil.process_iter(attrs, ad_value=None):
            try:
                info = proc.info
                total_count += 1

                status = info.get("status", "unknown")
                if status == psutil.STATUS_ZOMBIE:
                    zombie_count += 1
                elif status == psutil.STATUS_RUNNING:
                    running_count += 1
                elif status == psutil.STATUS_SLEEPING:
                    sleeping_count += 1

                mem_info = info.get("memory_info")
                rss = mem_info.rss if mem_info else 0
                vms = mem_info.vms if mem_info else 0

                pid = info["pid"]
                name = info.get("name", "unknown")

                # Track RSS for leak detection (only sample every 30s, only if >10MB)
                should_sample_rss = (now - self._last_rss_sample) >= self._rss_sample_interval
                if should_sample_rss and rss > 10 * 1024 * 1024:  # Only track >10MB
                    self._rss_history[pid].append((now, rss))
                    # Keep only last 30 minutes
                    cutoff = now - 1800
                    self._rss_history[pid] = [
                        (t, r) for t, r in self._rss_history[pid]
                        if t > cutoff
                    ]

                # Check for icon
                has_icon = False
                if self.icon_resolver:
                    exe_basename = ""
                    if info.get("exe"):
                        import os
                        exe_basename = os.path.basename(info["exe"])
                    has_icon = self.icon_resolver.has_icon(exe_basename or name)

                # Build cmdline string
                cmdline = info.get("cmdline")
                cmdline_str = " ".join(cmdline) if cmdline else name

                proc_data = {
                    "pid": pid,
                    "name": name,
                    "username": info.get("username", "?"),
                    "cpu_percent": info.get("cpu_percent", 0) or 0,
                    "memory_percent": round(info.get("memory_percent", 0) or 0, 1),
                    "rss": rss,
                    "vms": vms,
                    "status": status,
                    "create_time": info.get("create_time", 0),
                    "cmdline": cmdline_str[:200],
                    "nice": info.get("nice", 0),
                    "num_threads": info.get("num_threads", 0),
                    "ppid": info.get("ppid", 0),
                    "has_icon": has_icon,
                    "is_zombie": status == psutil.STATUS_ZOMBIE,
                    "memory_leak": pid in self._leak_flagged,
                    "safety": get_process_safety(name),
                }

                processes.append(proc_data)

                if proc_data["is_zombie"]:
                    zombies.append(proc_data)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Update RSS sample timestamp
        if now - self._last_rss_sample >= self._rss_sample_interval:
            self._last_rss_sample = now

        # Periodic leak detection
        if now - self._last_leak_check > self._leak_check_interval:
            self._last_leak_check = now
            self._detect_leaks(now)

        # Clean up dead PIDs from history
        alive_pids = {p["pid"] for p in processes}
        dead_pids = set(self._rss_history.keys()) - alive_pids
        for pid in dead_pids:
            del self._rss_history[pid]
            self._leak_flagged.discard(pid)

        # Sort by CPU% descending by default
        processes.sort(key=lambda p: p["cpu_percent"], reverse=True)

        # Limit to top N processes to reduce WebSocket payload
        top_processes = processes[:self._max_process_list]

        return {
            "processes": top_processes,
            "summary": {
                "total": total_count,
                "running": running_count,
                "sleeping": sleeping_count,
                "zombie": zombie_count,
                "leak_count": len(self._leak_flagged),
            },
            "zombies": zombies,
        }

    def _detect_leaks(self, now: float):
        """Flag processes where RSS increased >50% over the last hour with no decrease."""
        for pid, history in self._rss_history.items():
            if len(history) < 10:
                continue

            # Get data from ~1 hour ago
            one_hour_ago = now - 3600
            old_entries = [(t, r) for t, r in history if t < one_hour_ago + 120]
            if not old_entries:
                continue

            old_rss = old_entries[0][1]
            current_rss = history[-1][1]

            if old_rss <= 0:
                continue

            increase_ratio = (current_rss - old_rss) / old_rss

            # Check if RSS has been monotonically increasing (with some tolerance)
            rss_values = [r for _, r in history[-30:]]  # Last 30 samples
            decreases = sum(1 for i in range(1, len(rss_values)) if rss_values[i] < rss_values[i-1])
            monotonic_ratio = decreases / max(len(rss_values) - 1, 1)

            if increase_ratio > 0.5 and monotonic_ratio < 0.15:
                self._leak_flagged.add(pid)
            else:
                self._leak_flagged.discard(pid)
