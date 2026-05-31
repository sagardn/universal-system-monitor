"""
Universal System Monitor — Network Actions

Control network services: Tailscale, WiFi, Bluetooth, Firewall, DNS.
Uses 3-tier privilege escalation: direct → sudo -n → pkexec.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess

logger = logging.getLogger("usm.actions.network")


async def handle_network_action(action: str, params: dict) -> dict:
    """Route network actions."""
    handlers = {
        "tailscale_up": _tailscale_up,
        "tailscale_down": _tailscale_down,
        "tailscale_status": _tailscale_status,
        "wifi_scan": _wifi_scan,
        "wifi_connect": _wifi_connect,
        "wifi_disconnect": _wifi_disconnect,
        "bluetooth_toggle": _bluetooth_toggle,
        "firewall_toggle": _firewall_toggle,
        "dns_flush": _dns_flush,
    }

    handler = handlers.get(action)
    if not handler:
        return {"target": "network", "action": action, "success": False,
                "message": f"Unknown action: {action}"}

    try:
        return await handler(params)
    except Exception as e:
        logger.exception("Network action %s failed", action)
        return {"target": "network", "action": action, "success": False,
                "message": str(e)}


# ─── Tailscale ────────────────────────────────────────────────────────────────

async def _tailscale_up(params: dict) -> dict:
    """Start Tailscale VPN."""
    ok, msg = await _run_privileged(["tailscale", "up"], timeout=15)
    return {"target": "network", "action": "tailscale_up", "success": ok,
            "message": msg or "✓ Tailscale connected"}


async def _tailscale_down(params: dict) -> dict:
    """Stop Tailscale VPN."""
    ok, msg = await _run_privileged(["tailscale", "down"], timeout=10)
    return {"target": "network", "action": "tailscale_down", "success": ok,
            "message": msg or "✓ Tailscale disconnected"}


async def _tailscale_status(params: dict) -> dict:
    """Get detailed Tailscale status."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "tailscale", "status", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            data = json.loads(stdout.decode())
            self_node = data.get("Self", {})
            peers = data.get("Peer", {})
            online_peers = sum(1 for p in peers.values() if p.get("Online"))
            return {
                "target": "network", "action": "tailscale_status",
                "success": True,
                "data": {
                    "connected": True,
                    "hostname": self_node.get("HostName", ""),
                    "ips": self_node.get("TailscaleIPs", []),
                    "os": self_node.get("OS", ""),
                    "peers_total": len(peers),
                    "peers_online": online_peers,
                    "tailnet": data.get("MagicDNSSuffix", ""),
                },
            }
    except Exception:
        pass
    return {"target": "network", "action": "tailscale_status",
            "success": True, "data": {"connected": False}}


# ─── WiFi ─────────────────────────────────────────────────────────────────────

async def _wifi_scan(params: dict) -> dict:
    """Scan for available WiFi networks."""
    try:
        # Rescan first
        await asyncio.create_subprocess_exec(
            "nmcli", "device", "wifi", "rescan",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(2)

        proc = await asyncio.create_subprocess_exec(
            "nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        networks = []
        seen = set()
        for line in stdout.decode().strip().split("\n"):
            parts = line.split(":")
            if len(parts) >= 4 and parts[0] and parts[0] not in seen:
                seen.add(parts[0])
                networks.append({
                    "ssid": parts[0],
                    "signal": int(parts[1]) if parts[1].isdigit() else 0,
                    "security": parts[2],
                    "in_use": parts[3] == "*",
                })
        networks.sort(key=lambda x: x["signal"], reverse=True)
        return {"target": "network", "action": "wifi_scan", "success": True,
                "data": {"networks": networks}}
    except Exception as e:
        return {"target": "network", "action": "wifi_scan", "success": False,
                "message": str(e)}


async def _wifi_connect(params: dict) -> dict:
    """Connect to a WiFi network."""
    ssid = params.get("ssid", "")
    password = params.get("password", "")
    if not ssid:
        return {"target": "network", "action": "wifi_connect", "success": False,
                "message": "SSID required"}

    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            return {"target": "network", "action": "wifi_connect", "success": True,
                    "message": f"✓ Connected to {ssid}"}
        return {"target": "network", "action": "wifi_connect", "success": False,
                "message": stderr.decode().strip() or stdout.decode().strip()}
    except Exception as e:
        return {"target": "network", "action": "wifi_connect", "success": False,
                "message": str(e)}


async def _wifi_disconnect(params: dict) -> dict:
    """Disconnect WiFi."""
    device = params.get("device", "wlan0")
    try:
        proc = await asyncio.create_subprocess_exec(
            "nmcli", "device", "disconnect", device,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return {"target": "network", "action": "wifi_disconnect", "success": True,
                    "message": f"✓ {device} disconnected"}
        return {"target": "network", "action": "wifi_disconnect", "success": False,
                "message": stderr.decode().strip()}
    except Exception as e:
        return {"target": "network", "action": "wifi_disconnect", "success": False,
                "message": str(e)}


# ─── Bluetooth ────────────────────────────────────────────────────────────────

async def _bluetooth_toggle(params: dict) -> dict:
    """Toggle Bluetooth power on/off."""
    enable = params.get("enable", True)
    action_str = "on" if enable else "off"
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "power", action_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        return {"target": "network", "action": "bluetooth_toggle", "success": True,
                "message": f"✓ Bluetooth {action_str}"}
    except Exception as e:
        return {"target": "network", "action": "bluetooth_toggle", "success": False,
                "message": str(e)}


# ─── Firewall ─────────────────────────────────────────────────────────────────

async def _firewall_toggle(params: dict) -> dict:
    """Toggle UFW firewall."""
    enable = params.get("enable", True)
    action_str = "enable" if enable else "disable"
    # UFW needs --force to avoid interactive prompt
    cmd = ["ufw", "--force", action_str] if enable else ["ufw", "disable"]
    ok, msg = await _run_privileged(cmd, timeout=10)
    return {"target": "network", "action": "firewall_toggle", "success": ok,
            "message": msg or f"✓ Firewall {action_str}d"}


# ─── DNS ──────────────────────────────────────────────────────────────────────

async def _dns_flush(params: dict) -> dict:
    """Flush DNS cache."""
    ok, msg = await _run_privileged(["resolvectl", "flush-caches"], timeout=5)
    return {"target": "network", "action": "dns_flush", "success": ok,
            "message": msg or "✓ DNS cache flushed"}


# ─── Privilege escalation helper ──────────────────────────────────────────────

async def _run_privileged(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """
    Run a command with privilege escalation.
    Tries: direct → sudo -n → pkexec.
    Returns (success, error_message_or_empty).
    """
    # Step 1: Try direct
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0:
            logger.info("Network action %s succeeded (direct)", cmd[0])
            return True, ""
    except (asyncio.TimeoutError, Exception):
        pass

    # Step 2: Try sudo -n
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-n", *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0:
            logger.info("Network action %s succeeded (sudo)", cmd[0])
            return True, ""
    except (asyncio.TimeoutError, Exception):
        pass

    # Step 3: Try pkexec
    try:
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"

        proc = await asyncio.create_subprocess_exec(
            "pkexec", *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode == 0:
            logger.info("Network action %s succeeded (pkexec)", cmd[0])
            return True, ""
        elif proc.returncode == 126:
            return False, "Authentication cancelled"
        else:
            return False, stderr.decode().strip() or f"Failed (exit {proc.returncode})"
    except asyncio.TimeoutError:
        return False, "Operation timed out"
    except Exception as e:
        return False, str(e)
