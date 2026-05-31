"""
Universal System Monitor — PipeWire Actions

Control volume, mute, and default output device via wpctl/pactl.
"""

import asyncio
import logging
import shutil

logger = logging.getLogger("usm.actions.pipewire")


async def handle_pipewire_action(action: str, params: dict) -> dict:
    """Handle PipeWire audio actions."""
    if action == "set_volume":
        node_id = params.get("node_id")
        volume = params.get("volume")
        if node_id is None or volume is None:
            return {"target": "audio", "action": action, "success": False,
                    "message": "node_id and volume required"}
        return await _set_volume(int(node_id), float(volume))

    elif action == "set_mute":
        node_id = params.get("node_id")
        mute = params.get("mute", True)
        if node_id is None:
            return {"target": "audio", "action": action, "success": False,
                    "message": "node_id required"}
        return await _set_mute(int(node_id), bool(mute))

    elif action == "toggle_mute":
        node_id = params.get("node_id")
        if node_id is None:
            return {"target": "audio", "action": action, "success": False,
                    "message": "node_id required"}
        return await _toggle_mute(int(node_id))

    elif action == "set_default_sink":
        node_id = params.get("node_id")
        if node_id is None:
            return {"target": "audio", "action": action, "success": False,
                    "message": "node_id required"}
        return await _set_default(int(node_id), "sink")

    elif action == "set_default_source":
        node_id = params.get("node_id")
        if node_id is None:
            return {"target": "audio", "action": action, "success": False,
                    "message": "node_id required"}
        return await _set_default(int(node_id), "source")

    return {"target": "audio", "action": action, "success": False,
            "message": f"Unknown action: {action}"}


async def _run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


async def _set_volume(node_id: int, volume: float) -> dict:
    """Set volume for a PipeWire node (0.0 - 1.5)."""
    volume = max(0.0, min(1.5, volume))
    vol_pct = int(volume * 100)

    # wpctl (WirePlumber) — most reliable
    wpctl = shutil.which("wpctl")
    if wpctl:
        rc, out, err = await _run([wpctl, "set-volume", str(node_id), f"{volume:.2f}"])
        if rc == 0:
            return {"target": "audio", "action": "set_volume", "success": True,
                    "message": f"Volume: {vol_pct}%"}

    # pactl fallback
    pactl = shutil.which("pactl")
    if pactl:
        rc, out, err = await _run([pactl, "set-sink-volume", str(node_id), f"{vol_pct}%"])
        if rc == 0:
            return {"target": "audio", "action": "set_volume", "success": True,
                    "message": f"Volume: {vol_pct}%"}

    return {"target": "audio", "action": "set_volume", "success": False,
            "message": "No audio control tool found (wpctl/pactl)"}


async def _set_mute(node_id: int, mute: bool) -> dict:
    """Mute/unmute a node."""
    wpctl = shutil.which("wpctl")
    if wpctl:
        val = "1" if mute else "0"
        rc, out, err = await _run([wpctl, "set-mute", str(node_id), val])
        if rc == 0:
            return {"target": "audio", "action": "set_mute", "success": True,
                    "message": "🔇 Muted" if mute else "🔊 Unmuted"}

    pactl = shutil.which("pactl")
    if pactl:
        val = "1" if mute else "0"
        rc, out, err = await _run([pactl, "set-sink-mute", str(node_id), val])
        if rc == 0:
            return {"target": "audio", "action": "set_mute", "success": True,
                    "message": "🔇 Muted" if mute else "🔊 Unmuted"}

    return {"target": "audio", "action": "set_mute", "success": False,
            "message": "No audio control tool found"}


async def _toggle_mute(node_id: int) -> dict:
    """Toggle mute on a node."""
    wpctl = shutil.which("wpctl")
    if wpctl:
        rc, out, err = await _run([wpctl, "set-mute", str(node_id), "toggle"])
        if rc == 0:
            return {"target": "audio", "action": "toggle_mute", "success": True,
                    "message": "Mute toggled"}

    return {"target": "audio", "action": "toggle_mute", "success": False,
            "message": "No audio control tool found"}


async def _set_default(node_id: int, kind: str) -> dict:
    """Set default sink or source."""
    wpctl = shutil.which("wpctl")
    if wpctl:
        rc, out, err = await _run([wpctl, "set-default", str(node_id)])
        if rc == 0:
            label = "output" if kind == "sink" else "input"
            return {"target": "audio", "action": f"set_default_{kind}", "success": True,
                    "message": f"Default {label} device changed"}

    return {"target": "audio", "action": f"set_default_{kind}", "success": False,
            "message": "Failed to set default device"}
