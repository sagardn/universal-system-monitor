"""
Universal System Monitor — Temperature & Fan Collector

Monitors CPU, GPU, and other hardware temperatures plus fan speeds
via Linux hwmon sysfs interface. Works on all distros.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os

logger = logging.getLogger("usm.collectors.thermal")


class ThermalCollector:
    """Collects temperature and fan speed data from hwmon sysfs."""

    channel = "thermal"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = getattr(config.intervals, "thermal", 3)

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
                logger.error("Thermal collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect all thermal data."""
        sensors = self._read_hwmon()
        zones = self._read_thermal_zones()
        fans = self._read_fans()

        # Extract key temperatures
        cpu_temp = self._find_cpu_temp(sensors, zones)
        gpu_temp = self._find_gpu_temp(sensors)

        # Find highest temp across all sensors
        all_temps = []
        for s in sensors:
            for t in s.get("temps", []):
                all_temps.append(t["value"])
        for z in zones:
            all_temps.append(z["temp"])

        return {
            "cpu_temp": cpu_temp,
            "gpu_temp": gpu_temp,
            "max_temp": max(all_temps) if all_temps else 0,
            "sensors": sensors,
            "thermal_zones": zones,
            "fans": fans,
        }

    def _read_hwmon(self) -> list[dict]:
        """Read all hwmon sensors."""
        sensors = []
        for hwmon_dir in sorted(glob.glob("/sys/class/hwmon/hwmon*/")):
            sensor = self._read_hwmon_device(hwmon_dir)
            if sensor and sensor.get("temps"):
                sensors.append(sensor)
        return sensors

    def _read_hwmon_device(self, path: str) -> dict | None:
        """Read a single hwmon device."""
        name = self._read_file(os.path.join(path, "name"), "").strip()
        if not name:
            return None

        sensor = {
            "name": name,
            "path": path,
            "temps": [],
            "fans": [],
        }

        # Read temperatures (temp1_input, temp2_input, etc.)
        for temp_file in sorted(glob.glob(os.path.join(path, "temp*_input"))):
            idx = os.path.basename(temp_file).replace("temp", "").replace("_input", "")
            try:
                value = int(self._read_file(temp_file, "0")) / 1000
                label_file = temp_file.replace("_input", "_label")
                label = self._read_file(label_file, f"temp{idx}").strip()
                crit_file = temp_file.replace("_input", "_crit")
                crit = int(self._read_file(crit_file, "0")) / 1000
                max_file = temp_file.replace("_input", "_max")
                temp_max = int(self._read_file(max_file, "0")) / 1000

                sensor["temps"].append({
                    "label": label,
                    "value": round(value, 1),
                    "critical": round(crit, 1) if crit > 0 else None,
                    "max": round(temp_max, 1) if temp_max > 0 else None,
                })
            except (ValueError, OSError):
                continue

        # Read fan speeds
        for fan_file in sorted(glob.glob(os.path.join(path, "fan*_input"))):
            idx = os.path.basename(fan_file).replace("fan", "").replace("_input", "")
            try:
                rpm = int(self._read_file(fan_file, "0"))
                label_file = fan_file.replace("_input", "_label")
                label = self._read_file(label_file, f"fan{idx}").strip()
                max_file = fan_file.replace("_input", "_max")
                max_rpm = int(self._read_file(max_file, "0"))

                sensor["fans"].append({
                    "label": label,
                    "rpm": rpm,
                    "max_rpm": max_rpm if max_rpm > 0 else None,
                    "percent": round(rpm / max_rpm * 100) if max_rpm > 0 else None,
                })
            except (ValueError, OSError):
                continue

        return sensor

    def _read_thermal_zones(self) -> list[dict]:
        """Read /sys/class/thermal zones."""
        zones = []
        for zone_dir in sorted(glob.glob("/sys/class/thermal/thermal_zone*/")):
            try:
                zone_type = self._read_file(os.path.join(zone_dir, "type"), "").strip()
                temp_str = self._read_file(os.path.join(zone_dir, "temp"), "0")
                temp = int(temp_str) / 1000

                zone = {
                    "name": zone_type,
                    "temp": round(temp, 1),
                    "trips": [],
                }

                # Read trip points
                for trip_file in sorted(glob.glob(os.path.join(zone_dir, "trip_point_*_temp"))):
                    idx = os.path.basename(trip_file).split("_")[2]
                    try:
                        trip_temp = int(self._read_file(trip_file, "0")) / 1000
                        trip_type_file = trip_file.replace("_temp", "_type")
                        trip_type = self._read_file(trip_type_file, "").strip()
                        if trip_temp > 0:
                            zone["trips"].append({
                                "type": trip_type,
                                "temp": round(trip_temp, 1),
                            })
                    except (ValueError, OSError):
                        continue

                zones.append(zone)
            except (ValueError, OSError):
                continue
        return zones

    def _read_fans(self) -> list[dict]:
        """Read all fan data across hwmon devices."""
        fans = []
        for hwmon_dir in sorted(glob.glob("/sys/class/hwmon/hwmon*/")):
            name = self._read_file(os.path.join(hwmon_dir, "name"), "").strip()
            for fan_file in sorted(glob.glob(os.path.join(hwmon_dir, "fan*_input"))):
                idx = os.path.basename(fan_file).replace("fan", "").replace("_input", "")
                try:
                    rpm = int(self._read_file(fan_file, "0"))
                    label_file = fan_file.replace("_input", "_label")
                    label = self._read_file(label_file, f"fan{idx}").strip()
                    max_file = fan_file.replace("_input", "_max")
                    max_rpm = int(self._read_file(max_file, "0"))

                    fans.append({
                        "device": name,
                        "label": label,
                        "rpm": rpm,
                        "max_rpm": max_rpm if max_rpm > 0 else None,
                        "percent": round(rpm / max_rpm * 100) if max_rpm > 0 else None,
                    })
                except (ValueError, OSError):
                    continue
        return fans

    @staticmethod
    def _find_cpu_temp(sensors: list[dict], zones: list[dict]) -> float:
        """Find CPU temperature from sensors or thermal zones."""
        # Check hwmon sensors first
        cpu_names = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cputemp")
        for s in sensors:
            if s["name"].lower() in cpu_names:
                temps = s.get("temps", [])
                if temps:
                    # Use "Tctl" or "Package" or first temp
                    for t in temps:
                        if any(x in t["label"].lower() for x in ("tctl", "package", "tdie")):
                            return t["value"]
                    return temps[0]["value"]

        # Fallback to thermal zones
        for z in zones:
            if any(x in z["name"].lower() for x in ("cpu", "x86_pkg", "soc")):
                return z["temp"]

        # Last resort: any thermal zone
        if zones:
            return zones[0]["temp"]
        return 0

    @staticmethod
    def _find_gpu_temp(sensors: list[dict]) -> float:
        """Find GPU temperature from sensors."""
        gpu_names = ("amdgpu", "nvidia", "nouveau", "i915", "xe", "radeon")
        for s in sensors:
            if s["name"].lower() in gpu_names:
                temps = s.get("temps", [])
                if temps:
                    for t in temps:
                        if "edge" in t["label"].lower() or "junction" in t["label"].lower():
                            return t["value"]
                    return temps[0]["value"]

        # Fallback: try nvidia-smi for NVIDIA GPUs
        import shutil
        import subprocess
        if shutil.which("nvidia-smi"):
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip().split("\n")[0])
            except Exception:
                pass
        return 0

    @staticmethod
    def _read_file(path: str, default: str = "") -> str:
        """Read a sysfs file safely."""
        try:
            with open(path) as f:
                return f.read().strip()
        except (OSError, PermissionError):
            return default
