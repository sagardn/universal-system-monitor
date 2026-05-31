"""
Universal System Monitor — Power Actions

Switch power profiles via powerprofilesctl or tuned.
"""

import asyncio
import logging
import shutil

logger = logging.getLogger("usm.actions.power")


async def handle_power_action(action: str, params: dict) -> dict:
    """Handle power management actions."""
    if action in ("set_profile", "set"):
        profile = params.get("profile", "")
        if not profile:
            return {"target": "power", "action": action, "success": False,
                    "message": "Profile name required"}
        return await _set_power_profile(profile)

    return {"target": "power", "action": action, "success": False,
            "message": f"Unknown action: {action}"}


async def _set_power_profile(profile: str) -> dict:
    """Switch power profile."""
    ppc = shutil.which("powerprofilesctl")
    if ppc:
        try:
            # powerprofilesctl is a Python script that needs system gi (PyGObject).
            # Use /usr/bin/python3 explicitly to bypass the venv python.
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/python3", ppc, "set", profile,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode == 0:
                return {"target": "power", "action": "set_profile", "success": True,
                        "message": f"✓ Power profile: {profile}"}
            else:
                return {"target": "power", "action": "set_profile", "success": False,
                        "message": f"Failed: {stderr.decode().strip()}"}
        except Exception as e:
            return {"target": "power", "action": "set_profile", "success": False,
                    "message": str(e)}

    tuned = shutil.which("tuned-adm")
    if tuned:
        try:
            proc = await asyncio.create_subprocess_exec(
                "pkexec", tuned, "profile", profile,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                return {"target": "power", "action": "set_profile", "success": True,
                        "message": f"Tuned profile set to: {profile}"}
        except Exception as e:
            pass

    return {"target": "power", "action": "set_profile", "success": False,
            "message": "No power profile manager found"}
