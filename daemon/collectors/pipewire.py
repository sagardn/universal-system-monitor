"""
Universal System Monitor — PipeWire Audio Collector

Monitors PipeWire audio nodes, active streams, volumes, and latency
via pw-dump JSON output.
"""

import asyncio
import json
import logging
import shutil
import subprocess

logger = logging.getLogger("usm.collectors.pipewire")


class PipeWireCollector:
    """Collects PipeWire audio pipeline data."""

    channel = "audio"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.pipewire
        self._pw_dump = shutil.which("pw-dump")
        self._pactl = shutil.which("pactl")
        self._wpctl = shutil.which("wpctl")

    async def run(self):
        """Main collector loop."""
        if not self._pw_dump and not self._pactl:
            logger.info("Neither pw-dump nor pactl found, audio collector disabled")
            return

        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("PipeWire collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect audio pipeline data."""
        if self._pw_dump:
            return self._collect_pipewire()
        return self._collect_pactl()

    def _collect_pipewire(self) -> dict:
        """Collect via pw-dump."""
        try:
            result = subprocess.run(
                [self._pw_dump],
                capture_output=True, text=True, timeout=5,
            )
            objects = json.loads(result.stdout)
        except Exception as e:
            logger.debug("pw-dump failed: %s", e)
            return {"backend": "pipewire", "status": "error", "error": str(e)}

        sinks = []
        sources = []
        streams = []

        for obj in objects:
            obj_type = obj.get("type", "")
            info = obj.get("info", {})
            props = info.get("props", {}) if isinstance(info, dict) else {}

            if obj_type == "PipeWire:Interface:Node":
                media_class = props.get("media.class", "")
                node_name = props.get("node.description", props.get("node.name", "Unknown"))
                node_id = obj.get("id", 0)

                # Get real volume from wpctl (pw-dump volume is stale/cubic)
                vol, muted = self._get_wpctl_volume(node_id)

                node_data = {
                    "id": node_id,
                    "name": node_name,
                    "media_class": media_class,
                    "state": info.get("state", "unknown") if isinstance(info, dict) else "unknown",
                    "volume": vol,
                    "mute": muted,
                    "format": props.get("audio.format", ""),
                    "rate": props.get("audio.rate", props.get("node.rate", "")),
                    "channels": props.get("audio.channels", ""),
                    "application": props.get("application.name", ""),
                    "app_icon": props.get("application.icon-name", ""),
                }

                if "Sink" in media_class or "Output" in media_class:
                    if "Stream" in media_class:
                        streams.append({**node_data, "direction": "output"})
                    else:
                        sinks.append(node_data)
                elif "Source" in media_class or "Input" in media_class:
                    if "Stream" in media_class:
                        streams.append({**node_data, "direction": "input"})
                    else:
                        sources.append(node_data)

        return {
            "backend": "pipewire",
            "status": "running",
            "sinks": sinks,
            "sources": sources,
            "streams": streams,
            "summary": {
                "sinks": len(sinks),
                "sources": len(sources),
                "active_streams": len([s for s in streams if s.get("state") == "running"]),
            },
        }

    def _collect_pactl(self) -> dict:
        """Fallback: collect via pactl."""
        sinks = []
        try:
            result = subprocess.run(
                [self._pactl, "list", "sinks", "short"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        sinks.append({
                            "id": int(parts[0]) if parts[0].isdigit() else 0,
                            "name": parts[1],
                            "state": parts[-1] if len(parts) > 4 else "unknown",
                        })
        except Exception:
            pass

        return {
            "backend": "pulseaudio",
            "status": "running" if sinks else "unknown",
            "sinks": sinks,
            "sources": [],
            "streams": [],
        }

    def _get_wpctl_volume(self, node_id: int) -> tuple[float, bool]:
        """Get real volume and mute state via wpctl (accurate linear volume)."""
        if not self._wpctl:
            return 1.0, False
        try:
            result = subprocess.run(
                [self._wpctl, "get-volume", str(node_id)],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                # Output: "Volume: 0.80" or "Volume: 0.80 [MUTED]"
                line = result.stdout.strip()
                muted = "[MUTED]" in line
                parts = line.split()
                if len(parts) >= 2:
                    vol = float(parts[1])
                    return round(vol, 3), muted
        except Exception:
            pass
        return 1.0, False
