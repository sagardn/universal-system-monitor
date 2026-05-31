"""
Universal System Monitor — Service Actions

Start/stop/restart/enable/disable systemd services.
Tries direct systemctl first, falls back to pkexec for privilege escalation.
"""

import asyncio
import logging
import os

logger = logging.getLogger("usm.actions.service")


async def handle_service_action(action: str, params: dict) -> dict:
    """Handle systemd service management actions."""
    service = params.get("service", params.get("name", ""))
    if not service:
        return {"target": "service", "action": action, "success": False,
                "message": "Service name required"}

    # Ensure .service suffix
    if not service.endswith(".service"):
        service_unit = f"{service}.service"
    else:
        service_unit = service
        service = service.replace(".service", "")

    valid_actions = {"start", "stop", "restart", "enable", "disable", "reload"}
    if action not in valid_actions:
        return {"target": "service", "action": action, "success": False,
                "message": f"Unknown action: {action}. Valid: {valid_actions}"}

    # For docker/containerd stop: also stop the .socket unit to prevent socket activation restart
    socket_units = []
    if action == "stop" and service in ("docker", "containerd"):
        socket_units = [f"{service}.socket"]

    result = await _systemctl_action(service, service_unit, action)

    # Stop socket units too
    if result.get("success") and socket_units:
        for sock in socket_units:
            await _systemctl_action(service, sock, "stop")

    return result


async def _systemctl_action(service_name: str, service_unit: str, action: str) -> dict:
    """Execute systemctl action, escalating privileges if needed."""

    # Step 1: Try direct systemctl (works if user has polkit rules or passwordless sudo)
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", action, service_unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode == 0:
            logger.info("Service %s: %s succeeded (direct)", service_name, action)
            return {"target": "service", "action": action, "success": True,
                    "message": f"✓ Service {service_name} {action}ed successfully",
                    "service": service_name}
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    # Step 2: Try sudo -n (non-interactive, passwordless)
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-n", "systemctl", action, service_unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode == 0:
            logger.info("Service %s: %s succeeded (sudo)", service_name, action)
            return {"target": "service", "action": action, "success": True,
                    "message": f"✓ Service {service_name} {action}ed successfully",
                    "service": service_name}
    except (asyncio.TimeoutError, Exception):
        pass

    # Step 3: Use pkexec (shows GUI auth dialog)
    try:
        # Set DISPLAY and XAUTHORITY so polkit agent can show GUI dialog
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"

        proc = await asyncio.create_subprocess_exec(
            "pkexec", "systemctl", action, service_unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode == 0:
            logger.info("Service %s: %s succeeded (pkexec)", service_name, action)
            return {"target": "service", "action": action, "success": True,
                    "message": f"✓ Service {service_name} {action}ed successfully",
                    "service": service_name}
        elif proc.returncode == 126:
            return {"target": "service", "action": action, "success": False,
                    "message": "Authentication cancelled by user",
                    "service": service_name}
        elif proc.returncode == 127:
            return {"target": "service", "action": action, "success": False,
                    "message": f"Failed to {action} {service_name}: authentication required but no polkit agent found",
                    "service": service_name}
        else:
            err_msg = stderr.decode().strip()
            return {"target": "service", "action": action, "success": False,
                    "message": f"Failed to {action} {service_name}: {err_msg}",
                    "service": service_name}

    except asyncio.TimeoutError:
        return {"target": "service", "action": action, "success": False,
                "message": f"Operation timed out — check if a polkit authentication dialog is waiting for your password",
                "service": service_name}
    except Exception as e:
        return {"target": "service", "action": action, "success": False,
                "message": str(e), "service": service_name}
