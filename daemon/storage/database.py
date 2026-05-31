"""
Universal System Monitor — SQLite Database

Async SQLite storage for historical metrics, process snapshots,
Docker metrics, and alert history. Includes auto-downsampling and purging.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import aiosqlite

logger = logging.getLogger("usm.storage")


class Database:
    """Async SQLite database for historical metrics."""

    def __init__(self, config):
        self.config = config
        self.db_path = config.db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Create database and tables."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")

        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                timestamp REAL NOT NULL,
                cpu_percent REAL,
                ram_percent REAL,
                swap_percent REAL,
                gpu_percent REAL,
                gpu_temp REAL,
                gpu_vram_percent REAL,
                battery_percent REAL,
                power_draw REAL
            );

            CREATE TABLE IF NOT EXISTS process_snapshots (
                timestamp REAL NOT NULL,
                pid INTEGER,
                name TEXT,
                cpu_percent REAL,
                ram_rss INTEGER
            );

            CREATE TABLE IF NOT EXISTS docker_metrics (
                timestamp REAL NOT NULL,
                container_id TEXT,
                cpu_percent REAL,
                mem_usage INTEGER,
                net_rx INTEGER,
                net_tx INTEGER
            );

            CREATE TABLE IF NOT EXISTS network_metrics (
                timestamp REAL NOT NULL,
                interface TEXT,
                rx_bytes_s REAL,
                tx_bytes_s REAL
            );

            CREATE TABLE IF NOT EXISTS alert_history (
                timestamp REAL NOT NULL,
                rule_name TEXT,
                severity TEXT,
                message TEXT,
                acknowledged INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_system_ts ON system_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_process_ts ON process_snapshots(timestamp);
            CREATE INDEX IF NOT EXISTS idx_docker_ts ON docker_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_network_ts ON network_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_alert_ts ON alert_history(timestamp);
        """)
        await self._db.commit()

        # Schedule periodic maintenance
        asyncio.create_task(self._maintenance_loop())
        logger.info("Database initialized: %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()

    async def store_system_metrics(self, data: dict):
        """Store system metrics snapshot."""
        if not self._db:
            return
        try:
            gpu = data.get("gpu", {}) if "gpu" in data else {}
            battery = data.get("battery", {}) if "battery" in data else {}
            await self._db.execute(
                "INSERT INTO system_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    data.get("cpu", {}).get("percent", 0),
                    data.get("memory", {}).get("percent", 0),
                    data.get("swap", {}).get("percent", 0),
                    gpu.get("utilization", {}).get("gpu", 0) if gpu else 0,
                    gpu.get("temperature", {}).get("current", 0) if gpu else 0,
                    gpu.get("memory", {}).get("percent", 0) if gpu else 0,
                    battery.get("capacity", 0) if battery else 0,
                    battery.get("power_watts", 0) if battery else 0,
                ),
            )
            await self._db.commit()
        except Exception as e:
            logger.debug("Store system metrics error: %s", e)

    async def store_gpu_metrics(self, data: dict):
        """Store GPU-specific metrics (merged into system_metrics for simplicity)."""
        # GPU data is stored via system collector's periodic update
        pass

    async def store_battery_metrics(self, data: dict):
        """Store battery metrics (merged into system_metrics)."""
        pass

    async def store_process_snapshots(self, processes: list[dict]):
        """Store top process snapshots for leak detection."""
        if not self._db:
            return
        try:
            now = time.time()
            # Only store top 20 by RSS
            top = sorted(processes, key=lambda p: p.get("rss", 0), reverse=True)[:20]
            await self._db.executemany(
                "INSERT INTO process_snapshots VALUES (?, ?, ?, ?, ?)",
                [(now, p["pid"], p["name"], p.get("cpu_percent", 0), p.get("rss", 0))
                 for p in top],
            )
            await self._db.commit()
        except Exception as e:
            logger.debug("Store process snapshots error: %s", e)

    async def store_docker_metrics(self, containers: list[dict]):
        """Store Docker container metrics."""
        if not self._db:
            return
        try:
            now = time.time()
            for c in containers:
                stats = c.get("stats")
                if stats:
                    await self._db.execute(
                        "INSERT INTO docker_metrics VALUES (?, ?, ?, ?, ?, ?)",
                        (now, c["id"], stats.get("cpu_percent", 0),
                         stats.get("memory_usage", 0),
                         stats.get("network_rx", 0), stats.get("network_tx", 0)),
                    )
            await self._db.commit()
        except Exception as e:
            logger.debug("Store docker metrics error: %s", e)

    async def store_alert(self, alert):
        """Store an alert in history."""
        if not self._db:
            return
        try:
            await self._db.execute(
                "INSERT INTO alert_history VALUES (?, ?, ?, ?, ?)",
                (alert.timestamp, alert.rule_name, alert.severity,
                 alert.message, int(alert.acknowledged)),
            )
            await self._db.commit()
        except Exception as e:
            logger.debug("Store alert error: %s", e)

    async def query_metrics(self, channel: str, from_ts=None, to_ts=None,
                            limit: int = 500) -> list[dict]:
        """Query historical metrics for a channel."""
        if not self._db:
            return []

        table_map = {
            "system": "system_metrics",
            "processes": "process_snapshots",
            "docker": "docker_metrics",
            "network": "network_metrics",
            "alerts": "alert_history",
        }

        table = table_map.get(channel)
        if not table:
            return []

        conditions = []
        params = []

        if from_ts:
            conditions.append("timestamp >= ?")
            params.append(float(from_ts))
        if to_ts:
            conditions.append("timestamp <= ?")
            params.append(float(to_ts))

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            cursor = await self._db.execute(
                f"SELECT * FROM {table} {where} ORDER BY timestamp DESC LIMIT ?",
                (*params, limit),
            )
            columns = [d[0] for d in cursor.description]
            rows = await cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error("Query error: %s", e)
            return []

    async def _maintenance_loop(self):
        """Periodic database maintenance: downsample and purge old data."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._downsample()
                await self._purge_old()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Maintenance error: %s", e)

    async def _downsample(self):
        """Downsample old data to reduce DB size."""
        if not self._db:
            return
        now = time.time()
        # Delete individual points older than 1 hour, keeping 1-minute averages
        one_hour_ago = now - 3600
        try:
            await self._db.execute(
                """DELETE FROM system_metrics
                   WHERE timestamp < ?
                   AND rowid NOT IN (
                       SELECT MIN(rowid) FROM system_metrics
                       WHERE timestamp < ?
                       GROUP BY CAST(timestamp / 60 AS INTEGER)
                   )""",
                (one_hour_ago, one_hour_ago),
            )
            await self._db.commit()
            logger.debug("Downsampled system_metrics older than 1 hour")
        except Exception as e:
            logger.debug("Downsample error: %s", e)

    async def _purge_old(self):
        """Delete data older than retention period."""
        if not self._db:
            return
        cutoff = time.time() - (self.config.retention_days * 86400)
        try:
            for table in ["system_metrics", "process_snapshots", "docker_metrics",
                          "network_metrics", "alert_history"]:
                await self._db.execute(
                    f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,)
                )
            await self._db.commit()
            await self._db.execute("PRAGMA optimize")
            logger.info("Purged data older than %d days", self.config.retention_days)
        except Exception as e:
            logger.debug("Purge error: %s", e)
