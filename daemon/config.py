"""
Universal System Monitor — Configuration Management

Dataclass-based configuration with JSON persistence.
Loads from ~/.config/usm/config.json, falls back to defaults.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class CollectorIntervals:
    """Polling intervals for each collector in seconds."""
    system: float = 1.0
    processes: float = 2.0
    gpu: float = 3.0
    docker: float = 5.0
    services: float = 10.0
    battery: float = 10.0
    network: float = 2.0
    security: float = 30.0
    pipewire: float = 3.0
    packages: float = 3600.0  # 1 hour
    btrfs: float = 60.0
    scheduler: float = 5.0
    cgroups: float = 5.0


@dataclass
class AlertThresholds:
    """Default alert thresholds."""
    cpu_percent: float = 90.0
    cpu_duration_secs: int = 30
    ram_percent: float = 85.0
    swap_percent: float = 50.0
    gpu_temp_celsius: float = 85.0
    disk_percent: float = 90.0
    battery_low_percent: float = 15.0
    battery_critical_percent: float = 5.0
    alert_cooldown_secs: int = 300  # 5 minutes


@dataclass
class StorageConfig:
    """SQLite storage configuration."""
    db_path: str = ""
    retention_days: int = 7
    downsample_1min_after_hours: int = 1
    downsample_5min_after_hours: int = 24
    downsample_15min_after_hours: int = 168  # 7 days

    def __post_init__(self):
        if not self.db_path:
            import platform as _plat
            _sys = _plat.system()
            if _sys == "Darwin":
                data_dir = Path.home() / "Library" / "Application Support" / "USM"
            elif _sys == "Windows":
                data_dir = Path(os.environ.get("APPDATA", Path.home())) / "USM"
            else:
                data_dir = Path.home() / ".local" / "share" / "usm"
            self.db_path = str(data_dir / "metrics.db")


@dataclass
class ServerConfig:
    """Web server configuration."""
    host: str = "127.0.0.1"
    port: int = 7777
    ws_heartbeat_secs: int = 30


@dataclass
class WatchdogConfig:
    """Process watchdog configuration."""
    enabled: bool = True
    check_interval_secs: int = 10
    watched_processes: list[str] = field(default_factory=list)
    auto_restart: bool = False


@dataclass
class ServiceFilters:
    """Service category filters."""
    databases: list[str] = field(default_factory=lambda: [
        "mysql", "mysqld", "mariadb", "postgresql", "postgres",
        "redis", "redis-server", "mongod", "mongodb", "memcached",
    ])
    web_servers: list[str] = field(default_factory=lambda: [
        "nginx", "apache2", "httpd", "caddy",
    ])
    docker: list[str] = field(default_factory=lambda: [
        "docker", "containerd",
    ])
    network: list[str] = field(default_factory=lambda: [
        "NetworkManager", "systemd-resolved", "sshd", "firewalld",
    ])
    audio: list[str] = field(default_factory=lambda: [
        "pipewire", "pipewire-pulse", "wireplumber",
    ])
    custom: list[str] = field(default_factory=list)


@dataclass
class Config:
    """Root configuration for Universal System Monitor."""
    server: ServerConfig = field(default_factory=ServerConfig)
    intervals: CollectorIntervals = field(default_factory=CollectorIntervals)
    thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    storage: StorageConfig = field(default_factory=StorageConfig)
    watchdog: WatchdogConfig = field(default_factory=WatchdogConfig)
    service_filters: ServiceFilters = field(default_factory=ServiceFilters)
    remote_daemons: list[str] = field(default_factory=list)  # ["host:port", ...]

    @classmethod
    def config_path(cls) -> Path:
        return Path.home() / ".config" / "usm" / "config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, falling back to defaults."""
        path = cls.config_path()
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                return cls._from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[config] Warning: failed to parse {path}: {e}, using defaults")
        return cls()

    def save(self):
        """Persist current config to disk."""
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Recursively build config from a dict, merging with defaults."""
        cfg = cls()
        if "server" in data:
            cfg.server = ServerConfig(**{
                k: v for k, v in data["server"].items()
                if k in ServerConfig.__dataclass_fields__
            })
        if "intervals" in data:
            cfg.intervals = CollectorIntervals(**{
                k: v for k, v in data["intervals"].items()
                if k in CollectorIntervals.__dataclass_fields__
            })
        if "thresholds" in data:
            cfg.thresholds = AlertThresholds(**{
                k: v for k, v in data["thresholds"].items()
                if k in AlertThresholds.__dataclass_fields__
            })
        if "storage" in data:
            cfg.storage = StorageConfig(**{
                k: v for k, v in data["storage"].items()
                if k in StorageConfig.__dataclass_fields__
            })
        if "watchdog" in data:
            cfg.watchdog = WatchdogConfig(**{
                k: v for k, v in data["watchdog"].items()
                if k in WatchdogConfig.__dataclass_fields__
            })
        if "service_filters" in data:
            cfg.service_filters = ServiceFilters(**{
                k: v for k, v in data["service_filters"].items()
                if k in ServiceFilters.__dataclass_fields__
            })
        if "remote_daemons" in data:
            cfg.remote_daemons = data["remote_daemons"]
        return cfg


def ensure_dirs(config: Config):
    """Create necessary directories."""
    db_dir = Path(config.storage.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    config.config_path().parent.mkdir(parents=True, exist_ok=True)
