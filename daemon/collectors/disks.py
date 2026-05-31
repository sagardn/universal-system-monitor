"""
Universal System Monitor — Disk Health (SMART) Collector

Monitors disk health using smartctl or sysfs. Shows SMART attributes,
temperature, health status, and estimated lifespan for SSDs.
Works on all distros with smartmontools installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import glob
import os
import re
import shutil
import subprocess

from daemon.utils.sudo import sudo_prefix

logger = logging.getLogger("usm.collectors.disks")


class DiskHealthCollector:
    """Collects disk health data via smartctl and sysfs."""

    channel = "disks"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = getattr(config.intervals, "disks", 60)  # Check every 60s
        self._smartctl = shutil.which("smartctl")

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
                logger.error("Disk health collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect disk health for all block devices."""
        disks = self._get_block_devices()
        health_data = []

        for disk in disks:
            info = self._get_disk_info(disk)
            if info:
                health_data.append(info)

        # Summary
        total = len(health_data)
        healthy = sum(1 for d in health_data if d.get("health") == "PASSED")
        warnings = sum(1 for d in health_data if d.get("health") == "WARNING")
        failed = sum(1 for d in health_data if d.get("health") == "FAILED")

        return {
            "disks": health_data,
            "summary": {
                "total": total,
                "healthy": healthy,
                "warnings": warnings,
                "failed": failed,
            },
            "smartctl_available": bool(self._smartctl),
        }

    def _get_block_devices(self) -> list[str]:
        """Get list of physical block devices (not partitions)."""
        devices = []
        try:
            result = subprocess.run(
                ["lsblk", "-dnpo", "NAME,TYPE"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "disk":
                    devices.append(parts[0])
        except Exception as e:
            logger.debug("lsblk failed: %s", e)
            # Fallback
            for dev in glob.glob("/sys/block/sd*") + glob.glob("/sys/block/nvme*"):
                name = os.path.basename(dev)
                if not any(c.isdigit() for c in name.replace("nvme", "").split("n")[0]):
                    devices.append(f"/dev/{name}")
        return devices

    def _get_disk_info(self, device: str) -> dict | None:
        """Get health info for a single disk."""
        info = {
            "device": device,
            "name": os.path.basename(device),
        }

        # Try smartctl first (most reliable)
        if self._smartctl:
            smart = self._get_smart_data(device)
            if smart:
                info.update(smart)
                return info

        # Fallback to sysfs
        sysfs = self._get_sysfs_data(device)
        if sysfs:
            info.update(sysfs)
            return info

        return info

    def _get_smart_data(self, device: str) -> dict | None:
        """Get SMART data via smartctl."""
        try:
            # Try without sudo first, then with sudo -n
            for cmd_prefix in [[], sudo_prefix()] if sudo_prefix() else [[]]:
                result = subprocess.run(
                    cmd_prefix + [self._smartctl, "-a", "--json", device],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode in (0, 4):  # 4 = SMART error, but data available
                    break
                if result.returncode == 1 and "Permission denied" not in result.stderr:
                    break

            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                return self._parse_smart_text(device)

            # Extract info
            dev_info = data.get("device", {})
            model_name = data.get("model_name", "")
            serial = data.get("serial_number", "")
            fw_ver = data.get("firmware_version", "")
            form_factor = data.get("form_factor", {}).get("name", "")

            # Health
            smart_status = data.get("smart_status", {})
            health = "PASSED" if smart_status.get("passed", True) else "FAILED"

            # Temperature
            temp_data = data.get("temperature", {})
            temp_current = temp_data.get("current", 0)

            # Capacity
            user_capacity = data.get("user_capacity", {})
            capacity_bytes = user_capacity.get("bytes", 0)
            capacity_gb = round(capacity_bytes / (1000**3), 1) if capacity_bytes > 0 else 0

            # Power on hours
            power_on = data.get("power_on_time", {})
            power_hours = power_on.get("hours", 0)

            # Rotation rate (0 for SSD)
            rotation = data.get("rotation_rate", 0)
            is_ssd = rotation == 0

            # SMART attributes
            attrs = []
            attr_table = data.get("ata_smart_attributes", {}).get("table", [])
            for attr in attr_table:
                attrs.append({
                    "id": attr.get("id", 0),
                    "name": attr.get("name", ""),
                    "value": attr.get("value", 0),
                    "worst": attr.get("worst", 0),
                    "thresh": attr.get("thresh", 0),
                    "raw_value": attr.get("raw", {}).get("string", ""),
                    "flags": attr.get("flags", {}).get("string", ""),
                })

            # NVMe specific
            nvme_attrs = data.get("nvme_smart_health_information_log", {})
            nvme_percentage_used = nvme_attrs.get("percentage_used", None)
            nvme_data_read = nvme_attrs.get("data_units_read", 0)
            nvme_data_written = nvme_attrs.get("data_units_written", 0)

            # SSD lifespan estimate
            lifespan_pct = None
            if nvme_percentage_used is not None:
                lifespan_pct = max(0, 100 - nvme_percentage_used)
            else:
                # Check SSD Wear Leveling Count or Media Wearout Indicator
                for attr in attrs:
                    if attr["id"] in (177, 233, 173):  # Wear leveling
                        lifespan_pct = attr["value"]
                        break

            result_data = {
                "model": model_name,
                "serial": serial,
                "firmware": fw_ver,
                "form_factor": form_factor,
                "type": "NVMe" if "nvme" in device else ("SSD" if is_ssd else "HDD"),
                "capacity_gb": capacity_gb,
                "health": health,
                "temperature": temp_current,
                "power_on_hours": power_hours,
                "power_on_days": round(power_hours / 24, 1) if power_hours > 0 else 0,
                "attributes": attrs[:15],  # Top 15 most relevant
                "is_ssd": is_ssd,
                "lifespan_percent": lifespan_pct,
                "interface": dev_info.get("protocol", ""),
            }

            # NVMe extra
            if nvme_percentage_used is not None:
                result_data["nvme"] = {
                    "percentage_used": nvme_percentage_used,
                    "data_read_tb": round(nvme_data_read * 512000 / 1e12, 2),
                    "data_written_tb": round(nvme_data_written * 512000 / 1e12, 2),
                    "available_spare": nvme_attrs.get("available_spare", 0),
                    "critical_warning": nvme_attrs.get("critical_warning", 0),
                }

            return result_data

        except Exception as e:
            logger.debug("smartctl failed for %s: %s", device, e)
            return None

    def _parse_smart_text(self, device: str) -> dict | None:
        """Fallback: parse smartctl text output."""
        try:
            for cmd_prefix in [[], sudo_prefix()] if sudo_prefix() else [[]]:
                result = subprocess.run(
                    cmd_prefix + [self._smartctl, "-a", device],
                    capture_output=True, text=True, timeout=15,
                )
                if result.stdout:
                    break

            text = result.stdout
            if not text:
                return None

            info = {"model": "", "health": "UNKNOWN", "type": "Unknown"}

            # Model
            m = re.search(r'Device Model:\s+(.+)', text)
            if m:
                info["model"] = m.group(1).strip()

            # Health
            m = re.search(r'SMART overall-health.*?:\s+(\S+)', text)
            if m:
                info["health"] = m.group(1)

            # Temp
            m = re.search(r'Temperature_Celsius.*?(\d+)', text)
            if m:
                info["temperature"] = int(m.group(1))

            return info
        except Exception:
            return None

    def _get_sysfs_data(self, device: str) -> dict | None:
        """Get basic disk info from sysfs (no smartctl needed)."""
        dev_name = os.path.basename(device)
        sysfs_base = f"/sys/block/{dev_name}"
        if not os.path.exists(sysfs_base):
            return None

        info = {"type": "Unknown", "health": "UNKNOWN"}

        # Model
        model_file = os.path.join(sysfs_base, "device", "model")
        if os.path.exists(model_file):
            try:
                with open(model_file) as f:
                    info["model"] = f.read().strip()
            except OSError:
                pass

        # Size
        size_file = os.path.join(sysfs_base, "size")
        if os.path.exists(size_file):
            try:
                with open(size_file) as f:
                    sectors = int(f.read().strip())
                    info["capacity_gb"] = round(sectors * 512 / (1000**3), 1)
            except (OSError, ValueError):
                pass

        # Rotational (0 = SSD, 1 = HDD)
        rot_file = os.path.join(sysfs_base, "queue", "rotational")
        if os.path.exists(rot_file):
            try:
                with open(rot_file) as f:
                    is_ssd = f.read().strip() == "0"
                    info["is_ssd"] = is_ssd
                    info["type"] = "NVMe" if "nvme" in dev_name else ("SSD" if is_ssd else "HDD")
            except OSError:
                pass

        return info if info.get("model") else None
