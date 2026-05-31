"""
Universal System Monitor — Process Watchdog

Watches specific processes and alerts if they crash or restart.
Optionally auto-restarts via Polkit.
"""

from __future__ import annotations

import asyncio
import logging
import time

import psutil

logger = logging.getLogger("usm.alerts.watchdog")


class ProcessWatchdog:
    """Watches configured processes for crashes and restarts."""

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        # {process_name: {"pid": int, "since": float, "status": "running"|"down"}}
        self._state: dict[str, dict] = {}

    async def run(self):
        """Main watchdog loop."""
        if not self.config.watchdog.enabled:
            logger.info("Process watchdog disabled")
            return

        interval = self.config.watchdog.check_interval_secs
        logger.info("Watchdog watching: %s", self.config.watchdog.watched_processes)

        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._check)
                # Broadcast state
                await self.ws_manager.broadcast_event("watchdog", {
                    "processes": self._get_status(),
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Watchdog error: %s", e)
            await asyncio.sleep(interval)

    def _check(self):
        """Check all watched processes."""
        now = time.time()
        for name in self.config.watchdog.watched_processes:
            pid = self._find_process(name)
            prev = self._state.get(name)

            if pid:
                if prev is None:
                    # First detection
                    self._state[name] = {"pid": pid, "since": now, "status": "running"}
                elif prev["status"] == "down":
                    # Process came back
                    self._state[name] = {"pid": pid, "since": now, "status": "running"}
                    logger.info("Watchdog: %s is back (PID %d)", name, pid)
                elif prev["pid"] != pid:
                    # Process restarted (different PID)
                    self._state[name] = {"pid": pid, "since": now, "status": "running"}
                    logger.warning("Watchdog: %s restarted (PID %d -> %d)", name, prev["pid"], pid)
            else:
                if prev and prev["status"] == "running":
                    # Process crashed
                    self._state[name] = {"pid": 0, "since": now, "status": "down"}
                    logger.warning("Watchdog: %s is DOWN", name)
                elif prev is None:
                    self._state[name] = {"pid": 0, "since": now, "status": "down"}

    @staticmethod
    def _find_process(name: str) -> int:
        """Find a running process by name."""
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] == name:
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return 0

    def _get_status(self) -> list[dict]:
        """Get current watchdog status."""
        now = time.time()
        result = []
        for name, state in self._state.items():
            result.append({
                "name": name,
                "status": state["status"],
                "pid": state["pid"],
                "uptime": now - state["since"] if state["status"] == "running" else 0,
                "downtime": now - state["since"] if state["status"] == "down" else 0,
            })
        return result

    async def handle_action(self, action: str, params: dict) -> dict:
        """Handle watchdog actions."""
        if action == "add_watch":
            name = params.get("process", "")
            if name and name not in self.config.watchdog.watched_processes:
                self.config.watchdog.watched_processes.append(name)
                return {"target": "watchdog", "action": action, "success": True,
                        "message": f"Now watching: {name}"}
        elif action == "remove_watch":
            name = params.get("process", "")
            if name in self.config.watchdog.watched_processes:
                self.config.watchdog.watched_processes.remove(name)
                self._state.pop(name, None)
                return {"target": "watchdog", "action": action, "success": True,
                        "message": f"Stopped watching: {name}"}
        elif action == "get_status":
            return {"target": "watchdog", "action": action, "success": True,
                    "data": self._get_status()}

        return {"target": "watchdog", "action": action, "success": False,
                "message": f"Unknown action: {action}"}
