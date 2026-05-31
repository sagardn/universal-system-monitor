"""
Universal System Monitor — Docker Actions

Start/stop/restart/kill/remove Docker containers via unix socket.
Start/stop Docker daemon via systemctl with privilege escalation.
"""

import asyncio
import logging
import os

import aiohttp

logger = logging.getLogger("usm.actions.docker")

DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_API_BASE = "http://localhost"


async def handle_docker_action(action: str, params: dict) -> dict:
    """Handle Docker container actions."""
    container_id = params.get("container_id", params.get("id", ""))

    if action == "start_daemon":
        return await _manage_docker_daemon("start")
    elif action == "stop_daemon":
        return await _manage_docker_daemon("stop")

    if not container_id:
        return {"target": "docker", "action": action, "success": False,
                "message": "container_id required"}

    valid_actions = {"start", "stop", "restart", "kill", "remove"}
    if action not in valid_actions:
        return {"target": "docker", "action": action, "success": False,
                "message": f"Unknown action: {action}. Valid: {valid_actions}"}

    return await _container_action(container_id, action)


async def _container_action(container_id: str, action: str) -> dict:
    """Execute a Docker container action via unix socket."""
    if not os.path.exists(DOCKER_SOCKET):
        return {"target": "docker", "action": action, "success": False,
                "message": "Docker socket not found. Is Docker running?"}

    try:
        connector = aiohttp.UnixConnector(path=DOCKER_SOCKET)
        async with aiohttp.ClientSession(connector=connector) as session:
            if action == "remove":
                url = f"{DOCKER_API_BASE}/containers/{container_id}?force=true"
                method = session.delete
            else:
                url = f"{DOCKER_API_BASE}/containers/{container_id}/{action}"
                method = session.post

            async with method(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status in (200, 204):
                    logger.info("Docker %s on %s succeeded", action, container_id)
                    return {"target": "docker", "action": action, "success": True,
                            "message": f"✓ Container {container_id[:12]} {action}ed"}
                elif resp.status == 304:
                    return {"target": "docker", "action": action, "success": True,
                            "message": "Container already in desired state"}
                elif resp.status == 404:
                    return {"target": "docker", "action": action, "success": False,
                            "message": f"Container {container_id[:12]} not found"}
                else:
                    body = await resp.text()
                    return {"target": "docker", "action": action, "success": False,
                            "message": f"Docker API error {resp.status}: {body[:200]}"}

    except Exception as e:
        logger.error("Docker action failed: %s", e)
        return {"target": "docker", "action": action, "success": False,
                "message": f"Error: {str(e)}"}


async def _manage_docker_daemon(operation: str) -> dict:
    """Start or stop Docker daemon — tries direct, sudo, then pkexec."""

    # Step 1: Try direct systemctl
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", operation, "docker",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return {"target": "docker", "action": f"{operation}_daemon", "success": True,
                    "message": f"✓ Docker daemon {operation}ed"}
    except (asyncio.TimeoutError, Exception):
        pass

    # Step 2: Try sudo -n (non-interactive)
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-n", "systemctl", operation, "docker",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return {"target": "docker", "action": f"{operation}_daemon", "success": True,
                    "message": f"✓ Docker daemon {operation}ed"}
    except (asyncio.TimeoutError, Exception):
        pass

    # Step 3: pkexec (GUI dialog)
    try:
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"

        proc = await asyncio.create_subprocess_exec(
            "pkexec", "systemctl", operation, "docker",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode == 0:
            return {"target": "docker", "action": f"{operation}_daemon", "success": True,
                    "message": f"✓ Docker daemon {operation}ed"}
        elif proc.returncode == 126:
            return {"target": "docker", "action": f"{operation}_daemon", "success": False,
                    "message": "Authentication cancelled by user"}
        else:
            return {"target": "docker", "action": f"{operation}_daemon", "success": False,
                    "message": f"Failed: {stderr.decode().strip()}"}

    except asyncio.TimeoutError:
        return {"target": "docker", "action": f"{operation}_daemon", "success": False,
                "message": "Timed out — check if a password dialog is waiting behind your windows"}
    except Exception as e:
        return {"target": "docker", "action": f"{operation}_daemon", "success": False,
                "message": str(e)}
