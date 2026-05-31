"""
Universal System Monitor — Startup Actions

Enable/disable autostart applications by modifying .desktop files.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from configparser import ConfigParser

logger = logging.getLogger("usm.actions.startup")


async def handle_startup_action(action: str, params: dict) -> dict:
    """Route startup actions."""
    handlers = {
        "toggle": _toggle_startup,
        "delete": _delete_startup,
    }

    handler = handlers.get(action)
    if not handler:
        return {"target": "startup", "action": action, "success": False,
                "message": f"Unknown action: {action}"}

    try:
        return await handler(params)
    except Exception as e:
        logger.exception("Startup action %s failed", action)
        return {"target": "startup", "action": action, "success": False,
                "message": str(e)}


async def _toggle_startup(params: dict) -> dict:
    """Enable or disable an autostart entry."""
    filename = params.get("filename", "")
    enable = params.get("enable", True)

    if not filename:
        return {"target": "startup", "action": "toggle", "success": False,
                "message": "Filename required"}

    user_dir = Path.home() / ".config" / "autostart"
    user_file = user_dir / filename
    system_file = Path("/etc/xdg/autostart") / filename

    # For desktop entries: toggle X-GNOME-Autostart-enabled
    target = user_file if user_file.exists() else system_file

    if not target.exists():
        return {"target": "startup", "action": "toggle", "success": False,
                "message": f"File not found: {filename}"}

    # If it's a system file, copy to user dir first
    if target == system_file:
        user_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(system_file), str(user_file))
        target = user_file

    def _do():
        cp = ConfigParser(interpolation=None)
        cp.read(str(target), encoding="utf-8")
        cp.set("Desktop Entry", "X-GNOME-Autostart-enabled", str(enable).lower())
        with open(target, "w") as f:
            cp.write(f)

    await asyncio.get_event_loop().run_in_executor(None, _do)

    state = "enabled" if enable else "disabled"
    return {"target": "startup", "action": "toggle", "success": True,
            "message": f"✓ {filename} {state}"}


async def _delete_startup(params: dict) -> dict:
    """Delete a user autostart entry."""
    filename = params.get("filename", "")
    if not filename:
        return {"target": "startup", "action": "delete", "success": False,
                "message": "Filename required"}

    user_file = Path.home() / ".config" / "autostart" / filename
    if not user_file.exists():
        return {"target": "startup", "action": "delete", "success": False,
                "message": "Only user autostart entries can be deleted"}

    def _do():
        user_file.unlink()

    await asyncio.get_event_loop().run_in_executor(None, _do)

    return {"target": "startup", "action": "delete", "success": True,
            "message": f"✓ {filename} removed"}
