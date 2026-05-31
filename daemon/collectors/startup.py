"""
Universal System Monitor — Startup Collector

Reads autostart applications from XDG autostart directories
and systemd user units.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from configparser import ConfigParser

logger = logging.getLogger("usm.collectors.startup")


class StartupCollector:
    """Collects startup application entries."""

    channel = "startup"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = 30  # Check every 30 seconds

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
                logger.exception("Startup collector error")
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect all autostart entries."""
        apps = []

        # XDG autostart dirs
        home = Path.home()
        user_dir = home / ".config" / "autostart"
        system_dirs = [
            Path("/etc/xdg/autostart"),
        ]

        # User autostart entries
        if user_dir.exists():
            for f in sorted(user_dir.glob("*.desktop")):
                entry = self._parse_desktop(f, user=True)
                if entry:
                    apps.append(entry)

        # System autostart entries
        for sdir in system_dirs:
            if sdir.exists():
                for f in sorted(sdir.glob("*.desktop")):
                    entry = self._parse_desktop(f, user=False)
                    if entry:
                        # Skip if user already has override
                        if not any(a["filename"] == f.name for a in apps):
                            apps.append(entry)

        # Systemd user units that are enabled
        try:
            import subprocess
            result = subprocess.run(
                ["systemctl", "--user", "list-unit-files", "--type=service", "--state=enabled", "--no-pager", "--no-legend"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0].replace(".service", "")
                    apps.append({
                        "filename": parts[0],
                        "name": name,
                        "comment": "systemd user service",
                        "enabled": True,
                        "user": True,
                        "type": "systemd",
                        "exec": "",
                        "icon": "",
                    })
        except Exception:
            pass

        return {
            "apps": apps,
            "count": len(apps),
            "enabled_count": sum(1 for a in apps if a["enabled"]),
        }

    @staticmethod
    def _parse_desktop(path: Path, user: bool) -> dict | None:
        """Parse a .desktop autostart file."""
        try:
            cp = ConfigParser(interpolation=None)
            cp.read(str(path), encoding="utf-8")

            if not cp.has_section("Desktop Entry"):
                return None

            get = lambda k, d="": cp.get("Desktop Entry", k, fallback=d)

            # Hidden entries
            if get("Hidden", "false").lower() == "true":
                return None

            # NoDisplay entries are still autostart, just hidden from menus
            enabled = get("X-GNOME-Autostart-enabled", "true").lower() != "false"

            return {
                "filename": path.name,
                "path": str(path),
                "name": get("Name", path.stem),
                "comment": get("Comment", ""),
                "exec": get("Exec", ""),
                "icon": get("Icon", ""),
                "enabled": enabled,
                "user": user,
                "type": "desktop",
            }
        except Exception:
            return None
