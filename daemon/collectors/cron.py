"""
Universal System Monitor — Cron Collector

Parses crontab entries for the current user and system cron.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess

logger = logging.getLogger("usm.collectors.cron")

CRON_PRESETS = {
    "@reboot": "At reboot",
    "@yearly": "Yearly (Jan 1, 00:00)",
    "@annually": "Yearly (Jan 1, 00:00)",
    "@monthly": "Monthly (1st, 00:00)",
    "@weekly": "Weekly (Sun, 00:00)",
    "@daily": "Daily (00:00)",
    "@midnight": "Daily (00:00)",
    "@hourly": "Every hour",
}


class CronCollector:
    """Collects cron job entries."""

    channel = "cron"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = 30

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
            except Exception:
                logger.exception("Cron collector error")
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect cron entries."""
        jobs = []

        # User crontab
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for i, line in enumerate(result.stdout.strip().split("\n")):
                    entry = self._parse_line(line, i, user=True)
                    if entry:
                        jobs.append(entry)
        except Exception:
            pass

        # System cron.d
        try:
            from pathlib import Path
            for cron_dir in [Path("/etc/cron.d")]:
                if cron_dir.exists():
                    for f in sorted(cron_dir.iterdir()):
                        if f.is_file() and not f.name.startswith("."):
                            try:
                                content = f.read_text()
                                for i, line in enumerate(content.strip().split("\n")):
                                    entry = self._parse_line(line, i, user=False, source=f.name)
                                    if entry:
                                        jobs.append(entry)
                            except Exception:
                                pass
        except Exception:
            pass

        return {
            "jobs": jobs,
            "count": len(jobs),
            "user_count": sum(1 for j in jobs if j["user"]),
            "system_count": sum(1 for j in jobs if not j["user"]),
        }

    def _parse_line(self, line: str, index: int, user: bool, source: str = "crontab") -> dict | None:
        """Parse a single crontab line."""
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            # Check for disabled jobs (commented out cron lines)
            if line.startswith("#") and len(line) > 1:
                inner = line[1:].strip()
                entry = self._parse_cron_expression(inner, index, user, source)
                if entry:
                    entry["enabled"] = False
                    return entry
            return None

        # Skip variable assignments (e.g. SHELL=/bin/bash)
        if "=" in line and not line[0].isdigit() and not line.startswith("@"):
            return None

        return self._parse_cron_expression(line, index, user, source)

    def _parse_cron_expression(self, line: str, index: int, user: bool, source: str) -> dict | None:
        """Parse an actual cron expression line."""
        # Handle @preset shortcuts
        for preset, desc in CRON_PRESETS.items():
            if line.startswith(preset):
                command = line[len(preset):].strip()
                return {
                    "id": f"{source}:{index}",
                    "schedule": preset,
                    "schedule_human": desc,
                    "command": command,
                    "enabled": True,
                    "user": user,
                    "source": source,
                    "raw": line,
                }

        # Standard 5-field cron: min hour dom month dow command
        parts = line.split(None, 5)
        if len(parts) >= 6:
            schedule = " ".join(parts[:5])
            command = parts[5]
            return {
                "id": f"{source}:{index}",
                "schedule": schedule,
                "schedule_human": self._humanize(parts[:5]),
                "command": command,
                "enabled": True,
                "user": user,
                "source": source,
                "raw": line,
            }

        return None

    @staticmethod
    def _humanize(fields: list) -> str:
        """Convert 5 cron fields to human-readable text."""
        minute, hour, dom, month, dow = fields

        if all(f == "*" for f in fields):
            return "Every minute"

        parts = []
        if minute == "0" and hour == "*":
            parts.append("Every hour")
        elif minute == "0" and hour == "0":
            parts.append("Daily at midnight")
        elif minute != "*" and hour != "*":
            parts.append(f"At {hour}:{minute.zfill(2)}")
        elif minute.startswith("*/"):
            parts.append(f"Every {minute[2:]} min")
        elif hour.startswith("*/"):
            parts.append(f"Every {hour[2:]} hours")
        else:
            parts.append(f"{minute} {hour}")

        if dom != "*":
            parts.append(f"on day {dom}")
        if month != "*":
            parts.append(f"in month {month}")
        if dow != "*":
            days = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed",
                    "4": "Thu", "5": "Fri", "6": "Sat", "7": "Sun"}
            day_name = days.get(dow, dow)
            parts.append(f"on {day_name}")

        return " ".join(parts)
