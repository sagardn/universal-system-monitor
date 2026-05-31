"""
Universal System Monitor — systemd Services Collector

Queries systemctl for service status, filters by category,
and fetches recent journal entries for each service.
Batches PID/memory lookups for performance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess

logger = logging.getLogger("usm.collectors.services")


class ServiceCollector:
    """Collects systemd service information."""

    channel = "services"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.services

    async def run(self):
        """Main collector loop."""
        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Service collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect systemd service data."""
        # Get all services
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all",
                 "--no-pager", "--output=json"],
                capture_output=True, text=True, timeout=10,
            )
            services_raw = json.loads(result.stdout) if result.stdout.strip() else []
        except Exception as e:
            logger.error("systemctl failed: %s", e)
            return {"services": [], "categories": {}}

        # Batch fetch PIDs and memory for ACTIVE services only
        active_names = [
            s.get("unit", "").replace(".service", "")
            for s in services_raw
            if s.get("active") == "active" and s.get("unit", "").endswith(".service")
        ]
        pid_map = self._batch_get_pids(active_names)
        mem_map = self._batch_get_memory(active_names)

        # Parse and categorize
        services = []
        categories = {
            "databases": [],
            "web_servers": [],
            "docker": [],
            "network": [],
            "audio": [],
            "custom": [],
            "other_active": [],
            "inactive": [],
        }

        filters = self.config.service_filters

        for svc in services_raw:
            unit = svc.get("unit", "")
            if not unit.endswith(".service"):
                continue

            name = unit.replace(".service", "")
            active_state = svc.get("active", "")
            service_data = {
                "name": name,
                "unit": unit,
                "description": svc.get("description", ""),
                "load": svc.get("load", ""),
                "active": active_state,
                "sub": svc.get("sub", ""),
                "pid": pid_map.get(name, 0),
                "memory": mem_map.get(name, 0),
            }

            services.append(service_data)

            # Categorize
            categorized = False
            for cat_name, cat_list in [
                ("databases", filters.databases),
                ("web_servers", filters.web_servers),
                ("docker", filters.docker),
                ("network", filters.network),
                ("audio", filters.audio),
                ("custom", filters.custom),
            ]:
                if any(f.lower() in name.lower() for f in cat_list):
                    categories[cat_name].append(service_data)
                    categorized = True
                    break

            if not categorized:
                if active_state in ("active", "failed"):
                    categories["other_active"].append(service_data)
                else:
                    categories["inactive"].append(service_data)

        # Sort: failed first, then active, then inactive
        def sort_key(s):
            order = {"failed": 0, "active": 1, "inactive": 2}
            return order.get(s["active"], 3)

        services.sort(key=sort_key)
        for cat in categories.values():
            cat.sort(key=sort_key)

        # Summary
        summary = {
            "total": len(services),
            "active": sum(1 for s in services if s["active"] == "active"),
            "inactive": sum(1 for s in services if s["active"] == "inactive"),
            "failed": sum(1 for s in services if s["active"] == "failed"),
        }

        return {
            "services": services,
            "categories": categories,
            "summary": summary,
        }

    def _batch_get_pids(self, names: list[str]) -> dict[str, int]:
        """Batch get MainPID for multiple services in one call."""
        if not names:
            return {}
        result = {}
        try:
            units = [f"{n}.service" for n in names]
            proc = subprocess.run(
                ["systemctl", "show", "--property=MainPID", "--value", *units],
                capture_output=True, text=True, timeout=10,
            )
            lines = proc.stdout.strip().split("\n")
            for name, line in zip(names, lines):
                try:
                    pid = int(line.strip())
                    if pid > 0:
                        result[name] = pid
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            logger.debug("Batch PID lookup failed: %s", e)
        return result

    def _batch_get_memory(self, names: list[str]) -> dict[str, int]:
        """Batch get MemoryCurrent for multiple services in one call."""
        if not names:
            return {}
        result = {}
        try:
            units = [f"{n}.service" for n in names]
            proc = subprocess.run(
                ["systemctl", "show", "--property=MemoryCurrent", "--value", *units],
                capture_output=True, text=True, timeout=10,
            )
            lines = proc.stdout.strip().split("\n")
            for name, line in zip(names, lines):
                val = line.strip()
                if val and val != "[not set]" and val.isdigit():
                    result[name] = int(val)
        except Exception as e:
            logger.debug("Batch memory lookup failed: %s", e)
        return result

    @staticmethod
    def get_journal_entries(service_name: str, lines: int = 50) -> list[dict]:
        """Get recent journal entries for a service (called on demand)."""
        try:
            result = subprocess.run(
                ["journalctl", "-u", f"{service_name}.service",
                 "-n", str(lines), "--no-pager", "--output=json"],
                capture_output=True, text=True, timeout=5,
            )
            entries = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        entries.append({
                            "timestamp": entry.get("__REALTIME_TIMESTAMP", ""),
                            "message": entry.get("MESSAGE", ""),
                            "priority": entry.get("PRIORITY", "6"),
                        })
                    except json.JSONDecodeError:
                        continue
            return entries
        except Exception:
            return []
