"""
Universal System Monitor — Main Entry Point

Starts the asyncio event loop, initializes all collectors as background tasks,
starts the aiohttp web server, alert engine, and system tray icon.
Handles graceful shutdown on SIGINT/SIGTERM and config reload on SIGHUP.
Cross-platform: full features on Linux, basic monitoring on macOS/Windows.
"""

from __future__ import annotations

import asyncio
import signal
import sys
import os
import platform
import logging
from pathlib import Path

import aiohttp.web

from daemon.config import Config, ensure_dirs
from daemon.server import create_app, WebSocketManager
from daemon.storage.database import Database
from daemon.collectors.system import SystemCollector
from daemon.collectors.processes import ProcessCollector
from daemon.collectors.gpu import GPUCollector
from daemon.alerts.engine import AlertEngine
from daemon.alerts.watchdog import ProcessWatchdog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("usm")

PLATFORM = platform.system()  # 'Linux', 'Darwin', 'Windows'


def _get_collectors(config, ws_manager, db, icon_resolver):
    """Build collector list based on current platform."""
    # These work on ALL platforms (psutil cross-platform)
    collectors = [
        SystemCollector(config, ws_manager, db),
        ProcessCollector(config, ws_manager, db, icon_resolver),
        GPUCollector(config, ws_manager, db),
    ]

    if PLATFORM == "Linux":
        # Full Linux feature set
        from daemon.collectors.docker import DockerCollector
        from daemon.collectors.services import ServiceCollector
        from daemon.collectors.cgroups import CgroupsCollector
        from daemon.collectors.battery import BatteryCollector
        from daemon.collectors.network import NetworkCollector
        from daemon.collectors.security import SecurityCollector
        from daemon.collectors.pipewire import PipeWireCollector
        from daemon.collectors.packages import PackageCollector
        from daemon.collectors.btrfs import BtrfsCollector
        from daemon.collectors.scheduler import SchedulerCollector
        from daemon.collectors.thermal import ThermalCollector
        from daemon.collectors.disks import DiskHealthCollector
        from daemon.collectors.startup import StartupCollector
        from daemon.collectors.cron import CronCollector
        from daemon.collectors.cleanup import CleanupCollector
        from daemon.collectors.icons import IconResolver

        collectors.extend([
            DockerCollector(config, ws_manager, db),
            ServiceCollector(config, ws_manager),
            CgroupsCollector(config, ws_manager),
            BatteryCollector(config, ws_manager, db),
            NetworkCollector(config, ws_manager),
            SecurityCollector(config, ws_manager),
            PipeWireCollector(config, ws_manager),
            PackageCollector(config, ws_manager),
            BtrfsCollector(config, ws_manager),
            SchedulerCollector(config, ws_manager),
            ThermalCollector(config, ws_manager),
            DiskHealthCollector(config, ws_manager),
            StartupCollector(config, ws_manager),
            CronCollector(config, ws_manager),
            CleanupCollector(config, ws_manager),
        ])
    else:
        # macOS / Windows — only add collectors that work cross-platform
        try:
            from daemon.collectors.battery import BatteryCollector
            collectors.append(BatteryCollector(config, ws_manager, db))
        except Exception:
            logger.debug("Battery collector not available on this platform")

        try:
            from daemon.collectors.docker import DockerCollector
            collectors.append(DockerCollector(config, ws_manager, db))
        except Exception:
            logger.debug("Docker collector not available on this platform")

        logger.info("Running in cross-platform mode (%s) — some features are Linux-only", PLATFORM)

    return collectors


class USMMonitor:
    """Main application controller."""

    def __init__(self):
        self.config = Config.load()
        ensure_dirs(self.config)
        self.db: Database | None = None
        self.ws_manager = WebSocketManager()
        self.icon_resolver = None
        self.collectors: list = []
        self.tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Initialize and start all subsystems."""
        logger.info("Starting Universal System Monitor v0.2.0 (%s)", PLATFORM)

        # Initialize database
        self.db = Database(self.config.storage)
        await self.db.initialize()
        logger.info("Database initialized at %s", self.config.storage.db_path)

        # Build icon cache (Linux only — reads .desktop files)
        if PLATFORM == "Linux":
            from daemon.collectors.icons import IconResolver
            self.icon_resolver = IconResolver()
            await asyncio.get_event_loop().run_in_executor(None, self.icon_resolver.build_cache)
            logger.info("Icon cache built: %d mappings", len(self.icon_resolver._cache))

        # Initialize collectors based on platform
        self.collectors = _get_collectors(
            self.config, self.ws_manager, self.db, self.icon_resolver
        )

        # Initialize alert engine
        self.alert_engine = AlertEngine(self.config, self.ws_manager, self.db)
        self.watchdog = ProcessWatchdog(self.config, self.ws_manager)

        # Start collector background tasks
        for collector in self.collectors:
            task = asyncio.create_task(
                collector.run(),
                name=f"collector-{collector.channel}",
            )
            self.tasks.append(task)
            logger.info("Started collector: %s (interval: %ss)",
                        collector.channel, collector.interval)

        # Start alert engine
        self.tasks.append(asyncio.create_task(
            self.alert_engine.run(), name="alert-engine"
        ))
        self.tasks.append(asyncio.create_task(
            self.watchdog.run(), name="watchdog"
        ))

        # Start web server
        app = create_app(self)
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        site = aiohttp.web.TCPSite(
            runner,
            self.config.server.host,
            self.config.server.port,
        )
        await site.start()
        logger.info(
            "Dashboard available at http://%s:%d",
            self.config.server.host,
            self.config.server.port,
        )

        # Start system tray icon (optional, must never crash daemon)
        try:
            from daemon.tray import start_tray_thread
            self._tray_thread = start_tray_thread()
        except Exception:
            pass  # Tray is optional — never crash the daemon

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Cleanup
        logger.info("Shutting down...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await runner.cleanup()
        if self.db:
            await self.db.close()
        logger.info("Universal System Monitor stopped.")

    def request_shutdown(self):
        """Signal the main loop to shut down."""
        self._shutdown_event.set()

    def reload_config(self):
        """Reload configuration from disk."""
        logger.info("Reloading configuration...")
        self.config = Config.load()
        if self.icon_resolver:
            self.icon_resolver.build_cache()
        logger.info("Configuration reloaded.")


def main():
    """Entry point for the usm command."""
    monitor = USMMonitor()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Register signal handlers
    def handle_shutdown(sig, _frame):
        logger.info("Received signal %s", signal.Signals(sig).name)
        loop.call_soon_threadsafe(monitor.request_shutdown)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # SIGHUP only exists on Unix
    if hasattr(signal, "SIGHUP"):
        def handle_reload(sig, _frame):
            logger.info("Received SIGHUP, reloading config")
            loop.call_soon_threadsafe(monitor.reload_config)
        signal.signal(signal.SIGHUP, handle_reload)

    try:
        loop.run_until_complete(monitor.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    # Allow running as `python -m daemon.main` from project root
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    main()
