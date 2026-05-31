"""
Universal System Monitor — Snapshot Actions

Create/delete/restore BTRFS snapshots via Polkit.
"""

import asyncio
import logging
import shutil

logger = logging.getLogger("usm.actions.snapshot")


async def handle_snapshot_action(action: str, params: dict) -> dict:
    """Handle BTRFS snapshot actions."""
    snapper = shutil.which("snapper")
    if not snapper:
        return {"target": "snapshot", "action": action, "success": False,
                "message": "snapper not installed"}

    if action == "create":
        desc = params.get("description", "Manual snapshot from Universal System Monitor")
        return await _create_snapshot(snapper, desc)
    elif action == "delete":
        number = params.get("number")
        if not number:
            return {"target": "snapshot", "action": action, "success": False,
                    "message": "Snapshot number required"}
        return await _delete_snapshot(snapper, number)
    elif action == "restore":
        number = params.get("number")
        if not number:
            return {"target": "snapshot", "action": action, "success": False,
                    "message": "Snapshot number required"}
        return await _restore_snapshot(snapper, number)
    return {"target": "snapshot", "action": action, "success": False,
            "message": f"Unknown action: {action}"}


async def _create_snapshot(snapper: str, description: str) -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", snapper, "create", "-d", description,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            return {"target": "snapshot", "action": "create", "success": True,
                    "message": f"Snapshot created: {description}"}
        elif proc.returncode == 126:
            return {"target": "snapshot", "action": "create", "success": False,
                    "message": "Authentication cancelled"}
        return {"target": "snapshot", "action": "create", "success": False,
                "message": stderr.decode().strip()}
    except Exception as e:
        return {"target": "snapshot", "action": "create", "success": False, "message": str(e)}


async def _delete_snapshot(snapper: str, number) -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", snapper, "delete", str(number),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            return {"target": "snapshot", "action": "delete", "success": True,
                    "message": f"Snapshot {number} deleted"}
        return {"target": "snapshot", "action": "delete", "success": False,
                "message": stderr.decode().strip()}
    except Exception as e:
        return {"target": "snapshot", "action": "delete", "success": False, "message": str(e)}


async def _restore_snapshot(snapper: str, number) -> dict:
    try:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", snapper, "undochange", f"{number}..0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode == 0:
            return {"target": "snapshot", "action": "restore", "success": True,
                    "message": f"Snapshot {number} restored"}
        return {"target": "snapshot", "action": "restore", "success": False,
                "message": stderr.decode().strip()}
    except Exception as e:
        return {"target": "snapshot", "action": "restore", "success": False, "message": str(e)}
