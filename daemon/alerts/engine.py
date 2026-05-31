"""
Universal System Monitor — Alert Engine

Evaluates threshold-based alert rules against current system metrics.
Sends desktop notifications via notify-send and WebSocket events.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass

from daemon.alerts.rules import DEFAULT_RULES, AlertRule

logger = logging.getLogger("usm.alerts.engine")


@dataclass
class FiredAlert:
    """Record of a fired alert."""
    rule_name: str
    severity: str
    message: str
    timestamp: float
    acknowledged: bool = False


class AlertEngine:
    """Evaluates alert rules and dispatches notifications."""

    def __init__(self, config, ws_manager, db=None):
        self.config = config
        self.ws_manager = ws_manager
        self.db = db
        self.rules: list[AlertRule] = list(DEFAULT_RULES)
        self._last_fired: dict[str, float] = {}
        self._history: list[FiredAlert] = []
        self._notify_send = shutil.which("notify-send")

    async def run(self):
        """Main alert evaluation loop."""
        while True:
            try:
                await self._evaluate()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Alert engine error: %s", e)
            await asyncio.sleep(2)

    async def _evaluate(self):
        """Evaluate all enabled rules against latest data."""
        now = time.time()

        for rule in self.rules:
            if not rule.enabled:
                continue

            # Check cooldown
            last = self._last_fired.get(rule.name, 0)
            if now - last < self.config.thresholds.alert_cooldown_secs:
                continue

            # Get relevant data
            data = self.ws_manager.get_latest(rule.channel)
            if data is None:
                continue

            # Evaluate rule
            try:
                triggered, message = rule.evaluate(data, self.config.thresholds)
            except Exception as e:
                logger.debug("Rule %s eval error: %s", rule.name, e)
                continue

            if triggered:
                await self._fire_alert(rule, message, now)

    async def _fire_alert(self, rule: AlertRule, message: str, now: float):
        """Fire an alert: log, notify, broadcast."""
        self._last_fired[rule.name] = now

        alert = FiredAlert(
            rule_name=rule.name,
            severity=rule.severity,
            message=message,
            timestamp=now,
        )
        self._history.append(alert)

        # Keep history bounded
        if len(self._history) > 500:
            self._history = self._history[-250:]

        logger.warning("ALERT [%s] %s: %s", rule.severity, rule.name, message)

        # Desktop notification
        if self._notify_send:
            urgency = "critical" if rule.severity == "critical" else "normal"
            try:
                subprocess.Popen([
                    self._notify_send,
                    "--urgency", urgency,
                    "--app-name", "Universal System Monitor",
                    f"⚠️ {rule.name}",
                    message,
                ])
            except Exception:
                pass

        # WebSocket broadcast
        await self.ws_manager.broadcast_event("alert", {
            "rule": rule.name,
            "severity": rule.severity,
            "message": message,
            "timestamp": now,
        })

        # Store in DB
        if self.db:
            await self.db.store_alert(alert)

    def get_history(self) -> list[dict]:
        """Get alert history."""
        return [
            {
                "rule": a.rule_name,
                "severity": a.severity,
                "message": a.message,
                "timestamp": a.timestamp,
                "acknowledged": a.acknowledged,
            }
            for a in reversed(self._history)
        ]

    def get_rules(self) -> list[dict]:
        """Get all rules."""
        return [
            {"name": r.name, "severity": r.severity, "channel": r.channel,
             "description": r.description, "enabled": r.enabled}
            for r in self.rules
        ]


async def handle_alert_action(engine: AlertEngine, action: str, params: dict) -> dict:
    """Handle alert management actions."""
    if action == "get_history":
        return {"target": "alert", "action": action, "success": True,
                "data": engine.get_history()}
    elif action == "get_rules":
        return {"target": "alert", "action": action, "success": True,
                "data": engine.get_rules()}
    elif action == "toggle_rule":
        name = params.get("name", "")
        for rule in engine.rules:
            if rule.name == name:
                rule.enabled = not rule.enabled
                return {"target": "alert", "action": action, "success": True,
                        "message": f"Rule '{name}' {'enabled' if rule.enabled else 'disabled'}"}
        return {"target": "alert", "action": action, "success": False,
                "message": f"Rule '{name}' not found"}
    elif action == "acknowledge":
        idx = params.get("index", -1)
        if 0 <= idx < len(engine._history):
            engine._history[-(idx+1)].acknowledged = True
            return {"target": "alert", "action": action, "success": True,
                    "message": "Alert acknowledged"}

    return {"target": "alert", "action": action, "success": False,
            "message": f"Unknown action: {action}"}
