"""
Universal System Monitor — System Collector

Collects overall system metrics: CPU, RAM, swap, disk, network I/O,
temperatures, fans, load average, uptime, kernel info.
"""

from __future__ import annotations

import asyncio
import logging
import time
import platform
import os

import psutil

logger = logging.getLogger("usm.collectors.system")


class SystemCollector:
    """Collects system-wide metrics."""

    channel = "system"

    def __init__(self, config, ws_manager, db=None):
        self.config = config
        self.ws_manager = ws_manager
        self.db = db
        self.interval = config.intervals.system
        self._prev_net = None
        self._prev_disk_io = None
        self._prev_time = None
        self._boot_time = psutil.boot_time()
        # Cache static info (doesn't change at runtime)
        self._static_info = self._get_static_info()

    @staticmethod
    def _get_static_info() -> dict:
        """Read static system info once (cross-platform)."""
        import subprocess
        _platform = platform.system()
        info = {
            "hostname": platform.node(),
            "kernel": platform.release(),
            "arch": platform.machine(),
            "platform": _platform,
            "cpu_model": "",
            "distro": "",
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", os.environ.get("DESKTOP_SESSION", "")),
        }

        # CPU model — platform-specific
        if _platform == "Linux":
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.startswith("model name"):
                            info["cpu_model"] = line.split(":", 1)[1].strip()
                            break
            except OSError:
                pass
        elif _platform == "Darwin":
            try:
                out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
                info["cpu_model"] = out
            except Exception:
                info["cpu_model"] = platform.processor()
        else:
            info["cpu_model"] = platform.processor() or "Unknown"

        # Distro / OS name
        if _platform == "Linux":
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            info["distro"] = line.split("=", 1)[1].strip().strip('"')
                            break
            except OSError:
                pass
        elif _platform == "Darwin":
            try:
                out = subprocess.check_output(["sw_vers", "-productName"], text=True).strip()
                ver = subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip()
                info["distro"] = f"{out} {ver}"
            except Exception:
                info["distro"] = "macOS"
        elif _platform == "Windows":
            info["distro"] = f"Windows {platform.version()}"

        return info

    async def run(self):
        """Main collector loop."""
        # Prime CPU percent (first call always returns 0)
        psutil.cpu_percent(percpu=True)
        await asyncio.sleep(self.interval)

        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)

                # Store in database
                if self.db:
                    await self.db.store_system_metrics(data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("System collector error: %s", e)

            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect all system metrics (runs in thread pool)."""
        now = time.time()

        # CPU
        cpu_percent = psutil.cpu_percent(percpu=False)
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_freq = psutil.cpu_freq(percpu=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)
        try:
            load_avg = os.getloadavg()
        except (OSError, AttributeError):
            load_avg = (0.0, 0.0, 0.0)  # Not available on Windows

        # Memory
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk
        disk_usage = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_usage.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                })
            except PermissionError:
                continue

        # Disk I/O rates
        disk_io = psutil.disk_io_counters()
        disk_io_rate = {"read_bytes_s": 0, "write_bytes_s": 0}
        if self._prev_disk_io and self._prev_time:
            dt = now - self._prev_time
            if dt > 0:
                disk_io_rate["read_bytes_s"] = (disk_io.read_bytes - self._prev_disk_io.read_bytes) / dt
                disk_io_rate["write_bytes_s"] = (disk_io.write_bytes - self._prev_disk_io.write_bytes) / dt
        self._prev_disk_io = disk_io

        # Network I/O rates
        net_io = psutil.net_io_counters(pernic=True)
        net_interfaces = {}
        for iface, counters in net_io.items():
            rate = {"rx_bytes_s": 0, "tx_bytes_s": 0}
            if self._prev_net and iface in self._prev_net and self._prev_time:
                dt = now - self._prev_time
                if dt > 0:
                    prev = self._prev_net[iface]
                    rate["rx_bytes_s"] = (counters.bytes_recv - prev.bytes_recv) / dt
                    rate["tx_bytes_s"] = (counters.bytes_sent - prev.bytes_sent) / dt
            net_interfaces[iface] = {
                "bytes_recv": counters.bytes_recv,
                "bytes_sent": counters.bytes_sent,
                "packets_recv": counters.packets_recv,
                "packets_sent": counters.packets_sent,
                **rate,
            }
        self._prev_net = net_io

        # Temperatures
        temps = {}
        try:
            sensor_temps = psutil.sensors_temperatures()
            for name, entries in sensor_temps.items():
                temps[name] = [
                    {"label": e.label or f"sensor-{i}", "current": e.current,
                     "high": e.high, "critical": e.critical}
                    for i, e in enumerate(entries)
                ]
        except Exception:
            pass

        # Fans
        fans = {}
        try:
            sensor_fans = psutil.sensors_fans()
            for name, entries in sensor_fans.items():
                fans[name] = [
                    {"label": e.label or f"fan-{i}", "current": e.current}
                    for i, e in enumerate(entries)
                ]
        except Exception:
            pass

        # Users
        users = len(psutil.users())

        self._prev_time = now

        return {
            "cpu": {
                "percent": cpu_percent,
                "per_core": cpu_per_core,
                "freq_current": cpu_freq.current if cpu_freq else 0,
                "freq_min": cpu_freq.min if cpu_freq else 0,
                "freq_max": cpu_freq.max if cpu_freq else 0,
                "count_logical": cpu_count_logical,
                "count_physical": cpu_count_physical,
                "load_avg": list(load_avg),
            },
            "memory": {
                "total": mem.total,
                "available": mem.available,
                "used": mem.used,
                "cached": getattr(mem, "cached", 0),
                "buffers": getattr(mem, "buffers", 0),
                "percent": mem.percent,
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent,
            },
            "disk": {
                "partitions": disk_usage,
                "io_rate": disk_io_rate,
            },
            "network": net_interfaces,
            "temperatures": temps,
            "fans": fans,
            "uptime": now - self._boot_time,
            "users_count": users,
            **self._static_info,
        }
