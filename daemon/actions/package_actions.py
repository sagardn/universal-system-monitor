"""
Universal System Monitor — Package Actions

Trigger system updates via Polkit (pacman -Syu).
"""

import asyncio
import logging

logger = logging.getLogger("usm.actions.package")


async def handle_package_action(action: str, params: dict) -> dict:
    """Handle package management actions."""
    if action == "update_system":
        return await _run_update()
    return {"target": "package", "action": action, "success": False,
            "message": f"Unknown action: {action}"}


async def _run_update() -> dict:
    """Run system update via pkexec pacman -Syu."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", "pacman", "-Syu", "--noconfirm",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

        if proc.returncode == 0:
            return {"target": "package", "action": "update_system", "success": True,
                    "message": "System updated successfully",
                    "output": stdout.decode()[-500:]}
        elif proc.returncode == 126:
            return {"target": "package", "action": "update_system", "success": False,
                    "message": "Authentication cancelled"}
        else:
            return {"target": "package", "action": "update_system", "success": False,
                    "message": f"Update failed: {stderr.decode()[:300]}"}
    except asyncio.TimeoutError:
        return {"target": "package", "action": "update_system", "success": False,
                "message": "Update timed out (10min)"}
    except Exception as e:
        return {"target": "package", "action": "update_system", "success": False,
                "message": str(e)}
