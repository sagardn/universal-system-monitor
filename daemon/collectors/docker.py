"""
Universal System Monitor — Docker Collector

Connects directly to /var/run/docker.sock via aiohttp Unix connector
to list containers, fetch live stats, and detect daemon status.
"""

from __future__ import annotations

import asyncio
import logging
import json

import aiohttp

logger = logging.getLogger("usm.collectors.docker")

DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_API_BASE = "http://localhost"


class DockerCollector:
    """Collects Docker container data via Unix socket API."""

    channel = "docker"

    def __init__(self, config, ws_manager, db=None):
        self.config = config
        self.ws_manager = ws_manager
        self.db = db
        self.interval = config.intervals.docker
        self._session: aiohttp.ClientSession | None = None
        self._daemon_running = False

    async def _get_session(self) -> aiohttp.ClientSession | None:
        """Create or return an aiohttp session connected to Docker socket.
        
        IMPORTANT: Check if Docker is actually running before opening the socket,
        because opening docker.sock triggers systemd socket activation and
        restarts Docker even after the user stops it.
        """
        import os
        import subprocess

        if not os.path.exists(DOCKER_SOCKET):
            return None

        # Check if Docker daemon is actually running via systemctl
        # Don't just open the socket — that triggers socket activation!
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", "docker.service"],
                timeout=3, capture_output=True,
            )
            if result.returncode != 0:
                # Docker is not running — don't touch the socket
                self._daemon_running = False
                if self._session and not self._session.closed:
                    await self._session.close()
                self._session = None
                return None
        except Exception:
            pass  # If systemctl check fails, fall through to socket check

        if self._session is None or self._session.closed:
            try:
                connector = aiohttp.UnixConnector(path=DOCKER_SOCKET)
                self._session = aiohttp.ClientSession(connector=connector)
            except Exception as e:
                logger.error("Failed to connect to Docker socket: %s", e)
                return None
        return self._session

    async def run(self):
        """Main collector loop."""
        while True:
            try:
                data = await self._collect()
                await self.ws_manager.broadcast(self.channel, data)

                if self.db and data.get("daemon_running"):
                    await self.db.store_docker_metrics(data.get("containers", []))

            except asyncio.CancelledError:
                if self._session and not self._session.closed:
                    await self._session.close()
                break
            except Exception as e:
                logger.error("Docker collector error: %s", e)

            await asyncio.sleep(self.interval)

    async def _collect(self) -> dict:
        """Collect Docker data."""
        session = await self._get_session()
        if session is None:
            self._daemon_running = False
            return {
                "daemon_running": False,
                "containers": [],
                "images": [],
                "info": {},
            }

        try:
            # Check daemon
            async with session.get(f"{DOCKER_API_BASE}/version") as resp:
                if resp.status != 200:
                    self._daemon_running = False
                    return {"daemon_running": False, "containers": [], "images": [], "info": {}}
                version_info = await resp.json()

            self._daemon_running = True

            # List all containers
            async with session.get(f"{DOCKER_API_BASE}/containers/json?all=true") as resp:
                containers_raw = await resp.json()

            # Get stats for running containers
            containers = []
            for c in containers_raw:
                container = {
                    "id": c.get("Id", "")[:12],
                    "name": (c.get("Names", ["/unknown"])[0]).lstrip("/"),
                    "image": c.get("Image", ""),
                    "state": c.get("State", "unknown"),
                    "status": c.get("Status", ""),
                    "created": c.get("Created", 0),
                    "ports": self._format_ports(c.get("Ports", [])),
                    "labels": c.get("Labels", {}),
                    "stats": None,
                }

                # Fetch live stats for running containers
                if c.get("State") == "running":
                    try:
                        cid = c["Id"]
                        async with session.get(
                            f"{DOCKER_API_BASE}/containers/{cid}/stats?stream=false",
                            timeout=aiohttp.ClientTimeout(total=3),
                        ) as stats_resp:
                            if stats_resp.status == 200:
                                stats = await stats_resp.json()
                                container["stats"] = self._parse_stats(stats)
                    except Exception as e:
                        logger.debug("Failed to get stats for %s: %s", container["name"], e)

                containers.append(container)

            # Get images
            images = []
            try:
                async with session.get(f"{DOCKER_API_BASE}/images/json") as resp:
                    images_raw = await resp.json()
                    for img in images_raw:
                        tags = img.get("RepoTags", [])
                        images.append({
                            "id": img.get("Id", "")[:19],
                            "tags": tags,
                            "size": img.get("Size", 0),
                            "created": img.get("Created", 0),
                        })
            except Exception:
                pass

            # Docker info
            info = {}
            try:
                async with session.get(f"{DOCKER_API_BASE}/info") as resp:
                    info_raw = await resp.json()
                    info = {
                        "containers_running": info_raw.get("ContainersRunning", 0),
                        "containers_stopped": info_raw.get("ContainersStopped", 0),
                        "containers_paused": info_raw.get("ContainersPaused", 0),
                        "images": info_raw.get("Images", 0),
                        "storage_driver": info_raw.get("Driver", ""),
                        "server_version": info_raw.get("ServerVersion", ""),
                    }
            except Exception:
                pass

            return {
                "daemon_running": True,
                "containers": containers,
                "images": images,
                "info": info,
                "version": version_info.get("Version", ""),
            }

        except aiohttp.ClientError:
            self._daemon_running = False
            # Close broken session
            if self._session and not self._session.closed:
                await self._session.close()
            self._session = None
            return {"daemon_running": False, "containers": [], "images": [], "info": {}}

    def _parse_stats(self, stats: dict) -> dict:
        """Parse Docker container stats into a clean format."""
        # CPU
        cpu_delta = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) - \
                    stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
        system_delta = stats.get("cpu_stats", {}).get("system_cpu_usage", 0) - \
                       stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
        num_cpus = stats.get("cpu_stats", {}).get("online_cpus", 1) or 1
        cpu_percent = 0
        if system_delta > 0 and cpu_delta >= 0:
            cpu_percent = round((cpu_delta / system_delta) * num_cpus * 100, 2)

        # Memory
        mem_stats = stats.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0) - mem_stats.get("stats", {}).get("cache", 0)
        mem_limit = mem_stats.get("limit", 1)
        mem_percent = round(mem_usage / mem_limit * 100, 2) if mem_limit > 0 else 0

        # Network
        net_rx = 0
        net_tx = 0
        for iface_stats in stats.get("networks", {}).values():
            net_rx += iface_stats.get("rx_bytes", 0)
            net_tx += iface_stats.get("tx_bytes", 0)

        # Block I/O
        blkio = stats.get("blkio_stats", {}).get("io_service_bytes_recursive", []) or []
        block_read = sum(e.get("value", 0) for e in blkio if e.get("op") == "read")
        block_write = sum(e.get("value", 0) for e in blkio if e.get("op") == "write")

        return {
            "cpu_percent": cpu_percent,
            "memory_usage": mem_usage,
            "memory_limit": mem_limit,
            "memory_percent": mem_percent,
            "network_rx": net_rx,
            "network_tx": net_tx,
            "block_read": block_read,
            "block_write": block_write,
            "pids": stats.get("pids_stats", {}).get("current", 0),
        }

    @staticmethod
    def _format_ports(ports: list) -> list[str]:
        """Format Docker port mappings."""
        formatted = []
        for p in ports:
            private = p.get("PrivatePort", "")
            public = p.get("PublicPort", "")
            proto = p.get("Type", "tcp")
            if public:
                formatted.append(f"{public}:{private}/{proto}")
            else:
                formatted.append(f"{private}/{proto}")
        return formatted
