"""
Universal System Monitor — Battery & Power Collector

Reads battery status from /sys/class/power_supply/, detects power profiles,
calculates time remaining, battery health, and charge cycles.
"""

import asyncio
import logging
import subprocess
import shutil
from pathlib import Path

logger = logging.getLogger("usm.collectors.battery")

POWER_SUPPLY = Path("/sys/class/power_supply")


class BatteryCollector:
    """Collects battery and power management data."""

    channel = "battery"

    def __init__(self, config, ws_manager, db=None):
        self.config = config
        self.ws_manager = ws_manager
        self.db = db
        self.interval = config.intervals.battery
        self._has_battery = False
        self._powerprofilesctl = shutil.which("powerprofilesctl")
        self._tuned_adm = shutil.which("tuned-adm")

    async def run(self):
        """Main collector loop."""
        # Check if battery exists
        bat_dirs = list(POWER_SUPPLY.glob("BAT*"))
        if not bat_dirs:
            logger.info("No battery detected, battery collector disabled")
            # Still report power profile info
            while True:
                try:
                    data = await asyncio.get_event_loop().run_in_executor(
                        None, self._collect_power_only
                    )
                    await self.ws_manager.broadcast(self.channel, data)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Battery collector error: %s", e)
                await asyncio.sleep(self.interval)
            return

        self._has_battery = True
        self._bat_path = bat_dirs[0]
        logger.info("Battery detected: %s", self._bat_path.name)

        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
                if self.db:
                    await self.db.store_battery_metrics(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Battery collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect battery data from sysfs."""
        bat = self._bat_path

        capacity = self._read_int(bat / "capacity")
        status = self._read_str(bat / "status")  # Charging, Discharging, Full, Not charging

        # Power draw (watts)
        power_now = self._read_int(bat / "power_now")  # microwatts
        if power_now == 0:
            # Try current × voltage
            current_now = self._read_int(bat / "current_now")  # microamps
            voltage_now = self._read_int(bat / "voltage_now")  # microvolts
            if current_now and voltage_now:
                power_now = (current_now * voltage_now) // 1_000_000  # microwatts

        power_watts = power_now / 1_000_000 if power_now else 0

        # Energy for time remaining
        energy_now = self._read_int(bat / "energy_now")  # microwatt-hours
        energy_full = self._read_int(bat / "energy_full")
        energy_full_design = self._read_int(bat / "energy_full_design")

        # If energy values not available, try charge values
        if not energy_now:
            charge_now = self._read_int(bat / "charge_now")
            charge_full = self._read_int(bat / "charge_full")
            charge_full_design = self._read_int(bat / "charge_full_design")
            voltage = self._read_int(bat / "voltage_now") or 1_000_000
            energy_now = (charge_now * voltage) // 1_000_000 if charge_now else 0
            energy_full = (charge_full * voltage) // 1_000_000 if charge_full else 0
            energy_full_design = (charge_full_design * voltage) // 1_000_000 if charge_full_design else 0

        # Time remaining
        time_remaining_mins = 0
        if power_now > 0 and energy_now > 0:
            if status == "Discharging":
                time_remaining_mins = int((energy_now / power_now) * 60)
            elif status == "Charging" and energy_full > 0:
                remaining = energy_full - energy_now
                if remaining > 0:
                    time_remaining_mins = int((remaining / power_now) * 60)

        # Battery health
        health_percent = 0
        if energy_full_design > 0:
            health_percent = round(energy_full / energy_full_design * 100, 1)

        # Cycle count
        cycle_count = self._read_int(bat / "cycle_count")

        # AC adapter
        ac_online = False
        for ac_dir in POWER_SUPPLY.glob("AC*"):
            if self._read_str(ac_dir / "online") == "1":
                ac_online = True
                break
        # Also check ACAD, ADP
        for pattern in ["ACAD*", "ADP*"]:
            for ac_dir in POWER_SUPPLY.glob(pattern):
                if self._read_str(ac_dir / "online") == "1":
                    ac_online = True
                    break

        # Power profile
        profile_info = self._get_power_profile()

        return {
            "has_battery": True,
            "capacity": capacity,
            "status": status,
            "power_watts": round(power_watts, 2),
            "time_remaining_mins": time_remaining_mins,
            "energy_now_wh": round(energy_now / 1_000_000, 2),
            "energy_full_wh": round(energy_full / 1_000_000, 2),
            "energy_full_design_wh": round(energy_full_design / 1_000_000, 2),
            "health_percent": health_percent,
            "cycle_count": cycle_count,
            "ac_online": ac_online,
            "power_profile": profile_info,
        }

    def _collect_power_only(self) -> dict:
        """Collect only power profile info (no battery)."""
        return {
            "has_battery": False,
            "power_profile": self._get_power_profile(),
        }

    def _get_power_profile(self) -> dict:
        """Get current power profile."""
        if self._powerprofilesctl:
            try:
                # powerprofilesctl is a Python script needing system gi.
                # Run with /usr/bin/python3 to bypass venv.
                result = subprocess.run(
                    ["/usr/bin/python3", self._powerprofilesctl, "get"],
                    capture_output=True, text=True, timeout=3,
                )
                current = result.stdout.strip()

                # Get available profiles
                result2 = subprocess.run(
                    ["/usr/bin/python3", self._powerprofilesctl, "list"],
                    capture_output=True, text=True, timeout=3,
                )
                profiles = []
                for line in result2.stdout.split("\n"):
                    raw = line.rstrip()
                    if not raw:
                        continue
                    # Profile names: "  performance:" or "* balanced:"
                    # They end with ":" and are NOT indented with 4+ spaces
                    # Metadata lines: "    CpuDriver:  amd_pstate" (deeply indented, has value after colon)
                    stripped = raw.lstrip("* ")
                    if stripped.endswith(":") and ":" not in stripped[:-1]:
                        name = stripped[:-1].strip()
                        if name:
                            profiles.append(name)

                return {
                    "manager": "power-profiles-daemon",
                    "current": current,
                    "available": profiles if profiles else ["power-saver", "balanced", "performance"],
                }
            except Exception:
                pass

        if self._tuned_adm:
            try:
                result = subprocess.run(
                    [self._tuned_adm, "active"],
                    capture_output=True, text=True, timeout=3,
                )
                current = result.stdout.strip().split(":")[-1].strip()
                return {
                    "manager": "tuned",
                    "current": current,
                    "available": ["powersave", "balanced", "throughput-performance", "latency-performance"],
                }
            except Exception:
                pass

        return {"manager": "none", "current": "unknown", "available": []}

    @staticmethod
    def _read_int(path: Path) -> int:
        try:
            return int(path.read_text().strip())
        except (OSError, ValueError):
            return 0

    @staticmethod
    def _read_str(path: Path) -> str:
        try:
            return path.read_text().strip()
        except OSError:
            return ""
