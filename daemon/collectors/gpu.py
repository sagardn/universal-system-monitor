"""
Universal System Monitor — GPU Collector

Queries NVIDIA GPU via nvidia-smi XML output. Provides GPU utilization,
VRAM, temperature, power draw, clock speeds, per-process VRAM, and
thermal throttling detection. AMD fallback via sysfs.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

logger = logging.getLogger("usm.collectors.gpu")


class GPUCollector:
    """Collects GPU metrics from nvidia-smi or AMD sysfs."""

    channel = "gpu"

    def __init__(self, config, ws_manager, db=None):
        self.config = config
        self.ws_manager = ws_manager
        self.db = db
        self.interval = config.intervals.gpu
        self._nvidia_smi = shutil.which("nvidia-smi")
        self._gpu_type = self._detect_gpu()
        self._prev_clocks = None

    def _detect_gpu(self) -> str:
        """Detect available GPU type."""
        if self._nvidia_smi:
            return "nvidia"
        # Check AMD via sysfs
        amd_paths = glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")
        if amd_paths:
            return "amd"
        # Check Intel via sysfs or i915
        intel_paths = glob.glob("/sys/class/drm/card*/gt/gt*/rps_cur_freq_mhz")
        if not intel_paths:
            intel_paths = glob.glob("/sys/class/drm/card*/device/drm/card*/gt_cur_freq_mhz")
        if intel_paths:
            return "intel"
        # Also check lspci for Intel/AMD
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True, text=True, timeout=5,
            )
            if "VGA" in result.stdout or "3D" in result.stdout:
                for line in result.stdout.split("\n"):
                    if ("VGA" in line or "3D" in line):
                        if "Intel" in line:
                            return "intel"
                        if "AMD" in line or "ATI" in line:
                            return "amd"
        except Exception:
            pass
        return "none"

    async def run(self):
        """Main collector loop."""
        if self._gpu_type == "none":
            logger.info("No supported GPU detected, GPU collector disabled")
            return

        logger.info("GPU type detected: %s", self._gpu_type)

        while True:
            try:
                collectors = {
                    "nvidia": self._collect_nvidia,
                    "amd": self._collect_amd,
                    "intel": self._collect_intel,
                }
                collect_fn = collectors.get(self._gpu_type, self._collect_amd)
                data = await asyncio.get_event_loop().run_in_executor(
                    None, collect_fn
                )

                await self.ws_manager.broadcast(self.channel, data)

                if self.db:
                    await self.db.store_gpu_metrics(data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("GPU collector error: %s", e)

            await asyncio.sleep(self.interval)

    def _collect_nvidia(self) -> dict:
        """Collect NVIDIA GPU data via nvidia-smi XML."""
        # Get full GPU info
        try:
            result = subprocess.run(
                [self._nvidia_smi, "-q", "-x"],
                capture_output=True, text=True, timeout=15,
            )
            root = ET.fromstring(result.stdout)
        except Exception as e:
            logger.error("nvidia-smi XML failed: %s", e)
            return {"error": str(e), "type": "nvidia"}

        gpu = root.find("gpu")
        if gpu is None:
            return {"error": "No GPU found in XML", "type": "nvidia"}

        # Basic info
        name = gpu.findtext("product_name", "Unknown")
        driver = gpu.findtext("driver_version", "?")
        cuda = gpu.findtext("cuda_version", "?")

        # Temperature
        temp_node = gpu.find("temperature")
        temp_current = self._parse_value(temp_node, "gpu_temp", 0)
        temp_max = self._parse_value(temp_node, "gpu_temp_max_threshold", 100)
        temp_slowdown = self._parse_value(temp_node, "gpu_temp_slow_threshold", 90)

        # Fan
        fan_node = gpu.find("fan_speed")
        fan_speed = self._parse_text_value(fan_node, 0)

        # Power
        power_node = gpu.find("gpu_power_readings") or gpu.find("power_readings")
        power_draw = self._parse_value(power_node, "power_draw", 0)
        power_limit = self._parse_value(power_node, "enforced_power_limit", 0) or \
                      self._parse_value(power_node, "current_power_limit", 0)

        # Utilization
        util_node = gpu.find("utilization")
        gpu_util = self._parse_value(util_node, "gpu_util", 0)
        mem_util = self._parse_value(util_node, "memory_util", 0)

        # Memory
        mem_node = gpu.find("fb_memory_usage")
        mem_total = self._parse_value(mem_node, "total", 0)
        mem_used = self._parse_value(mem_node, "used", 0)
        mem_free = self._parse_value(mem_node, "free", 0)

        # Clocks
        clocks_node = gpu.find("clocks")
        clock_graphics = self._parse_value(clocks_node, "graphics_clock", 0)
        clock_mem = self._parse_value(clocks_node, "mem_clock", 0)

        max_clocks_node = gpu.find("max_clocks")
        max_clock_graphics = self._parse_value(max_clocks_node, "graphics_clock", 0)
        max_clock_mem = self._parse_value(max_clocks_node, "mem_clock", 0)

        # PCIe
        pci_node = gpu.find("pci")
        pcie_link = ""
        if pci_node is not None:
            link_node = pci_node.find("pci_gpu_link_info")
            if link_node:
                gen_node = link_node.find("pcie_gen")
                width_node = link_node.find("link_widths")
                if gen_node is not None and width_node is not None:
                    pcie_link = f"Gen{gen_node.findtext('current_link_gen', '?')} x{width_node.findtext('current_link_width', '?')}"

        # Thermal throttling detection
        throttling = False
        throttle_reason = ""
        if max_clock_graphics > 0 and clock_graphics > 0:
            ratio = clock_graphics / max_clock_graphics
            if ratio < 0.8 and temp_current > 80:
                throttling = True
                throttle_reason = f"Clocks at {ratio:.0%} of max, temp {temp_current}°C"

        # Per-process VRAM
        processes = self._get_nvidia_processes()

        return {
            "type": "nvidia",
            "name": name,
            "driver_version": driver,
            "cuda_version": cuda,
            "temperature": {
                "current": temp_current,
                "max": temp_max,
                "slowdown": temp_slowdown,
            },
            "fan_speed": fan_speed,
            "power": {
                "draw": power_draw,
                "limit": power_limit,
            },
            "utilization": {
                "gpu": gpu_util,
                "memory": mem_util,
            },
            "memory": {
                "total": mem_total,
                "used": mem_used,
                "free": mem_free,
                "percent": round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0,
            },
            "clocks": {
                "graphics": clock_graphics,
                "memory": clock_mem,
                "max_graphics": max_clock_graphics,
                "max_memory": max_clock_mem,
            },
            "pcie_link": pcie_link,
            "throttling": {
                "active": throttling,
                "reason": throttle_reason,
            },
            "processes": processes,
        }

    def _get_nvidia_processes(self) -> list[dict]:
        """Get ALL per-process GPU usage (compute + graphics) via pmon."""
        processes = []

        # Use pmon for SM%, MEM%, and FB (framebuffer / VRAM in MiB)
        try:
            result = subprocess.run(
                [self._nvidia_smi, "pmon", "-c", "1", "-s", "um"],
                capture_output=True, text=True, timeout=8,
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 10:
                    continue
                try:
                    pid = int(parts[1])
                    ptype = parts[2]        # C, G, or C+G
                    sm_pct = parts[3]        # SM utilization %
                    mem_pct = parts[4]       # Memory controller %
                    fb_mib = parts[9]        # Framebuffer (VRAM) MiB
                    # Command name is everything after column 11
                    cmd = " ".join(parts[11:]) if len(parts) > 11 else parts[10] if len(parts) > 10 else str(pid)

                    sm_val = int(sm_pct) if sm_pct != "-" else 0
                    mem_val = int(mem_pct) if mem_pct != "-" else 0
                    fb_val = int(fb_mib) if fb_mib != "-" else 0

                    # Resolve process name from PID
                    name = cmd
                    try:
                        import psutil
                        p = psutil.Process(pid)
                        name = p.name()
                    except Exception:
                        pass

                    processes.append({
                        "pid": pid,
                        "name": name,
                        "type": ptype,
                        "sm_percent": sm_val,
                        "mem_percent": mem_val,
                        "vram_mib": fb_val,
                    })
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            logger.debug("pmon failed: %s", e)

        # Sort by VRAM descending, then SM%
        processes.sort(key=lambda p: (p["vram_mib"], p["sm_percent"]), reverse=True)
        return processes

    def _collect_amd(self) -> dict:
        """Collect AMD GPU data from sysfs."""
        data = {"type": "amd", "name": self._get_gpu_name("AMD"), "processes": []}

        # GPU utilization
        busy_files = glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")
        if busy_files:
            try:
                with open(busy_files[0]) as f:
                    data["utilization"] = {"gpu": int(f.read().strip()), "memory": 0}
            except Exception:
                data["utilization"] = {"gpu": 0, "memory": 0}

        # VRAM
        vram_used_files = glob.glob("/sys/class/drm/card*/device/mem_info_vram_used")
        vram_total_files = glob.glob("/sys/class/drm/card*/device/mem_info_vram_total")
        if vram_used_files and vram_total_files:
            try:
                with open(vram_used_files[0]) as f:
                    used = int(f.read().strip())
                with open(vram_total_files[0]) as f:
                    total = int(f.read().strip())
                data["memory"] = {
                    "total": total // (1024 * 1024),
                    "used": used // (1024 * 1024),
                    "free": (total - used) // (1024 * 1024),
                    "percent": round(used / total * 100, 1) if total > 0 else 0,
                }
            except Exception:
                pass

        # Temperature
        temp_files = glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/temp1_input")
        if temp_files:
            try:
                with open(temp_files[0]) as f:
                    temp = int(f.read().strip()) // 1000
                data["temperature"] = {"current": temp, "max": 110, "slowdown": 95}
            except Exception:
                pass

        # Power draw (watts)
        power_files = glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/power1_average")
        if power_files:
            try:
                with open(power_files[0]) as f:
                    power_uw = int(f.read().strip())  # microwatts
                data["power"] = {"draw": round(power_uw / 1_000_000, 1), "limit": 0}
            except Exception:
                pass

        # Fan speed
        fan_files = glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/fan1_input")
        fan_max_files = glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/fan1_max")
        if fan_files:
            try:
                with open(fan_files[0]) as f:
                    fan_rpm = int(f.read().strip())
                fan_max = 0
                if fan_max_files:
                    with open(fan_max_files[0]) as f:
                        fan_max = int(f.read().strip())
                data["fan_speed"] = round(fan_rpm / fan_max * 100) if fan_max > 0 else 0
            except Exception:
                pass

        # Clock speeds
        sclk_files = glob.glob("/sys/class/drm/card*/device/pp_dpm_sclk")
        if sclk_files:
            try:
                with open(sclk_files[0]) as f:
                    for line in f:
                        if "*" in line:  # Active clock marked with *
                            match = re.search(r'(\d+)Mhz', line)
                            if match:
                                data["clocks"] = {
                                    "graphics": int(match.group(1)),
                                    "memory": 0, "max_graphics": 0, "max_memory": 0,
                                }
            except Exception:
                pass

        return data

    def _collect_intel(self) -> dict:
        """Collect Intel GPU data from sysfs."""
        data = {"type": "intel", "name": self._get_gpu_name("Intel"), "processes": []}

        # Frequency (current/max)
        freq_files = glob.glob("/sys/class/drm/card*/gt/gt*/rps_cur_freq_mhz")
        max_freq_files = glob.glob("/sys/class/drm/card*/gt/gt*/rps_max_freq_mhz")

        cur_freq = 0
        max_freq = 0
        if freq_files:
            try:
                with open(freq_files[0]) as f:
                    cur_freq = int(f.read().strip())
            except Exception:
                pass
        if max_freq_files:
            try:
                with open(max_freq_files[0]) as f:
                    max_freq = int(f.read().strip())
            except Exception:
                pass

        # Estimate utilization from frequency ratio
        gpu_util = round(cur_freq / max_freq * 100) if max_freq > 0 else 0
        data["utilization"] = {"gpu": gpu_util, "memory": 0}
        data["clocks"] = {
            "graphics": cur_freq, "memory": 0,
            "max_graphics": max_freq, "max_memory": 0,
        }

        # Temperature from hwmon
        for hwmon in glob.glob("/sys/class/hwmon/hwmon*/"):
            try:
                with open(os.path.join(hwmon, "name")) as f:
                    name = f.read().strip()
                if name in ("i915", "xe"):
                    temp_file = os.path.join(hwmon, "temp1_input")
                    if os.path.exists(temp_file):
                        with open(temp_file) as f:
                            temp = int(f.read().strip()) // 1000
                        data["temperature"] = {"current": temp, "max": 100, "slowdown": 90}
                    break
            except Exception:
                continue

        # Memory (shared with system RAM — report from i915 if available)
        meminfo_files = glob.glob("/sys/class/drm/card*/gt/gt*/mem_RP0_freq_mhz")
        # Intel iGPU shares system RAM, no dedicated VRAM to report
        data["memory"] = {"total": 0, "used": 0, "free": 0, "percent": 0}

        return data

    @staticmethod
    def _get_gpu_name(vendor: str) -> str:
        """Get GPU name from lspci."""
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if ("VGA" in line or "3D" in line) and vendor in line:
                    # Extract name after the colon, e.g.: "VGA compatible controller: AMD/ATI Navi 14 [Radeon RX 5500]"
                    match = re.search(r':\s+(.+?)\s*(?:\[|$)', line.split(":", 2)[-1])
                    if match:
                        return match.group(1).strip()
                    return line.split(":", 2)[-1].strip()
        except Exception:
            pass
        return f"{vendor} GPU"

    @staticmethod
    def _parse_value(parent, tag, default=0):
        """Parse a numeric value from XML, stripping units."""
        if parent is None:
            return default
        text = parent.findtext(tag, "")
        return GPUCollector._extract_number(text, default)

    @staticmethod
    def _parse_text_value(element, default=0):
        """Parse a numeric value from element text."""
        if element is None or not element.text:
            return default
        return GPUCollector._extract_number(element.text, default)

    @staticmethod
    def _extract_number(text: str, default=0):
        """Extract first number from text like '72 C' or '45.3 W'."""
        match = re.search(r"([\d.]+)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return default
