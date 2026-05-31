"""
Universal System Monitor — Web Server & WebSocket Manager

aiohttp web application that:
- Serves the static frontend from ../frontend/
- Manages WebSocket connections with channel subscriptions
- Dispatches action requests to the appropriate handlers
- Provides REST API for icons, history export, and config
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakSet

import aiohttp
from aiohttp import web

if TYPE_CHECKING:
    from daemon.main import USMMonitor

logger = logging.getLogger("usm.server")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# All available channels
CHANNELS = [
    "system", "processes", "gpu", "docker", "services", "cgroups",
    "battery", "network", "security", "audio", "packages", "snapshots",
    "scheduler", "alerts", "thermal", "disks", "startup", "cron", "cleanup",
]


class WebSocketClient:
    """Represents a connected WebSocket client with channel subscriptions."""

    def __init__(self, ws: web.WebSocketResponse):
        self.ws = ws
        self.subscriptions: set[str] = set()
        self.connected_at = time.time()

    async def send(self, channel: str, data: dict):
        """Send data to client if subscribed to channel."""
        if channel in self.subscriptions and not self.ws.closed:
            try:
                await self.ws.send_json({
                    "type": "data",
                    "channel": channel,
                    "timestamp": time.time(),
                    "data": data,
                })
            except (ConnectionResetError, asyncio.CancelledError):
                pass

    async def send_event(self, event_type: str, data: dict):
        """Send a non-channel event (alert, action_result, etc)."""
        if not self.ws.closed:
            try:
                await self.ws.send_json({
                    "type": event_type,
                    "timestamp": time.time(),
                    "data": data,
                })
            except (ConnectionResetError, asyncio.CancelledError):
                pass


class WebSocketManager:
    """Manages all WebSocket connections and broadcasts data."""

    def __init__(self):
        self._clients: set[WebSocketClient] = set()
        self._latest: dict[str, dict] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def add_client(self, client: WebSocketClient):
        self._clients.add(client)
        logger.info("Client connected (%d total)", len(self._clients))

    def remove_client(self, client: WebSocketClient):
        self._clients.discard(client)
        logger.info("Client disconnected (%d remaining)", len(self._clients))

    async def broadcast(self, channel: str, data: dict):
        """Broadcast data to all clients subscribed to channel."""
        # Don't cache large channels (processes can be 100KB+)
        if channel not in ("processes",):
            self._latest[channel] = data
        if not self._clients:
            return
        tasks = [client.send(channel, data) for client in self._clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_event(self, event_type: str, data: dict):
        """Broadcast an event to all connected clients."""
        tasks = [client.send_event(event_type, data) for client in self._clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_latest(self, channel: str) -> dict | None:
        """Get the latest data for a channel."""
        return self._latest.get(channel)


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket connections."""
    monitor: USMMonitor = request.app["monitor"]
    ws = web.WebSocketResponse(heartbeat=monitor.config.server.ws_heartbeat_secs)
    await ws.prepare(request)

    client = WebSocketClient(ws)
    monitor.ws_manager.add_client(client)

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                    await handle_ws_message(monitor, client, payload)
                except json.JSONDecodeError:
                    await client.send_event("error", {"message": "Invalid JSON"})
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("WebSocket error: %s", ws.exception())
    finally:
        monitor.ws_manager.remove_client(client)

    return ws


async def handle_ws_message(monitor: "USMMonitor", client: WebSocketClient, payload: dict):
    """Route incoming WebSocket messages."""
    msg_type = payload.get("type")

    if msg_type == "subscribe":
        channels = payload.get("channels", [])
        for ch in channels:
            if ch in CHANNELS:
                client.subscriptions.add(ch)
                # Send latest data immediately
                latest = monitor.ws_manager.get_latest(ch)
                if latest:
                    await client.send(ch, latest)
        logger.debug("Client subscribed to: %s", client.subscriptions)

    elif msg_type == "unsubscribe":
        channels = payload.get("channels", [])
        for ch in channels:
            client.subscriptions.discard(ch)

    elif msg_type == "action":
        await handle_action(monitor, client, payload)

    elif msg_type == "get_config":
        from dataclasses import asdict
        await client.send_event("config", asdict(monitor.config))

    elif msg_type == "set_config":
        # Update config from client
        try:
            new_config = payload.get("config", {})
            # Merge into current config and save
            import dataclasses
            current = dataclasses.asdict(monitor.config)
            _deep_merge(current, new_config)
            monitor.config = Config._from_dict(current)
            monitor.config.save()
            await client.send_event("action_result", {
                "action": "set_config",
                "success": True,
                "message": "Configuration saved",
            })
        except Exception as e:
            await client.send_event("action_result", {
                "action": "set_config",
                "success": False,
                "message": str(e),
            })


async def handle_action(monitor: "USMMonitor", client: WebSocketClient, payload: dict):
    """Dispatch action requests to appropriate handlers."""
    target = payload.get("target")
    action = payload.get("action")
    params = payload.get("params", {})

    result = {"target": target, "action": action, "success": False, "message": "Unknown target"}

    try:
        if target == "process":
            from daemon.actions.process_actions import handle_process_action
            result = await handle_process_action(action, params)

        elif target == "docker":
            from daemon.actions.docker_actions import handle_docker_action
            result = await handle_docker_action(action, params)

        elif target == "service":
            from daemon.actions.service_actions import handle_service_action
            result = await handle_service_action(action, params)

        elif target in ("power", "power_profile"):
            from daemon.actions.power_actions import handle_power_action
            result = await handle_power_action(action, params)

        elif target == "package":
            from daemon.actions.package_actions import handle_package_action
            result = await handle_package_action(action, params)

        elif target == "snapshot":
            from daemon.actions.snapshot_actions import handle_snapshot_action
            result = await handle_snapshot_action(action, params)

        elif target == "audio":
            from daemon.actions.pipewire_actions import handle_pipewire_action
            result = await handle_pipewire_action(action, params)

        elif target == "network":
            from daemon.actions.network_actions import handle_network_action
            result = await handle_network_action(action, params)

        elif target == "speedtest":
            from daemon.actions.speedtest_actions import handle_speedtest_action
            result = await handle_speedtest_action(action, params)

        elif target == "startup":
            from daemon.actions.startup_actions import handle_startup_action
            result = await handle_startup_action(action, params)

        elif target == "cron":
            from daemon.actions.cron_actions import handle_cron_action
            result = await handle_cron_action(action, params)

        elif target == "cleanup":
            from daemon.actions.cleanup_actions import handle_cleanup_action
            result = await handle_cleanup_action(action, params)

        elif target == "alert":
            from daemon.alerts.engine import handle_alert_action
            result = await handle_alert_action(monitor.alert_engine, action, params)

        elif target == "watchdog":
            result = await monitor.watchdog.handle_action(action, params)

    except Exception as e:
        logger.exception("Action failed: %s/%s", target, action)
        result = {"target": target, "action": action, "success": False, "message": str(e)}

    # Ensure response target/action match the request (frontend matches callbacks by these)
    result["target"] = target
    result["action"] = action

    await client.send_event("action_result", result)


# --- REST API Handlers ---

async def handle_icon(request: web.Request) -> web.Response:
    """Serve process icon by name."""
    monitor: USMMonitor = request.app["monitor"]
    name = request.match_info["name"]
    icon_path = monitor.icon_resolver.resolve(name)

    if icon_path and Path(icon_path).exists():
        return web.FileResponse(icon_path)
    # Return a transparent 1x1 PNG as fallback
    return web.Response(
        body=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
             b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
             b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
             b'\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
        content_type="image/png",
    )


async def handle_export(request: web.Request) -> web.Response:
    """Export historical data as CSV or JSON."""
    monitor: USMMonitor = request.app["monitor"]
    channel = request.match_info["channel"]
    fmt = request.query.get("format", "json")
    from_ts = request.query.get("from")
    to_ts = request.query.get("to")

    if not monitor.db:
        return web.json_response({"error": "Database not available"}, status=503)

    data = await monitor.db.query_metrics(channel, from_ts, to_ts)

    if fmt == "csv":
        import csv
        import io
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return web.Response(
            text=output.getvalue(),
            content_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=usm_{channel}.csv"},
        )
    else:
        return web.json_response(data)


async def handle_history(request: web.Request) -> web.Response:
    """Get historical data for charts."""
    monitor: USMMonitor = request.app["monitor"]
    channel = request.match_info["channel"]
    from_ts = request.query.get("from")
    to_ts = request.query.get("to")
    limit = int(request.query.get("limit", "500"))

    if not monitor.db:
        return web.json_response({"error": "Database not available"}, status=503)

    data = await monitor.db.query_metrics(channel, from_ts, to_ts, limit=limit)
    return web.json_response(data)


def _deep_merge(base: dict, override: dict):
    """Deep merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def create_app(monitor: "USMMonitor") -> web.Application:
    """Create and configure the aiohttp web application."""
    app = web.Application()
    app["monitor"] = monitor

    # WebSocket
    app.router.add_get("/ws", websocket_handler)

    # REST API
    app.router.add_get("/api/icons/{name}", handle_icon)
    app.router.add_get("/api/export/{channel}", handle_export)
    app.router.add_get("/api/history/{channel}", handle_history)

    # Static frontend files (Vite build output)
    if FRONTEND_DIR.exists():
        # Serve index.html for root
        app.router.add_get("/", lambda r: web.FileResponse(FRONTEND_DIR / "index.html"))
        # Vite puts bundled CSS/JS in assets/
        if (FRONTEND_DIR / "assets").exists():
            app.router.add_static("/assets/", FRONTEND_DIR / "assets", show_index=False)
        # Catch-all for SPA routing (must be last)
        app.router.add_get("/{path:.*}", _spa_fallback)
    else:
        logger.warning("Frontend not built. Run 'bun run build' in frontend/. Dir: %s", FRONTEND_DIR)

    return app


async def _spa_fallback(request: web.Request) -> web.Response:
    """Serve index.html for any unmatched route (SPA client-side routing)."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return web.FileResponse(index)
    return web.Response(text="Frontend not found", status=404)
