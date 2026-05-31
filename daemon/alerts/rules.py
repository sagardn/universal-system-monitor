"""
Universal System Monitor — Alert Rules

Default threshold-based alert rules for system monitoring.
Each rule evaluates latest channel data against configured thresholds.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class AlertRule:
    """An alert rule definition."""
    name: str
    description: str
    severity: str  # info, warning, critical
    channel: str
    enabled: bool
    evaluate: Callable  # (data, thresholds) -> (bool, str)


def _cpu_high(data, thresholds):
    cpu = data.get("cpu", {}).get("percent", 0)
    if cpu > thresholds.cpu_percent:
        return True, f"CPU usage at {cpu:.1f}% (threshold: {thresholds.cpu_percent}%)"
    return False, ""


def _ram_high(data, thresholds):
    ram = data.get("memory", {}).get("percent", 0)
    if ram > thresholds.ram_percent:
        return True, f"RAM usage at {ram:.1f}% (threshold: {thresholds.ram_percent}%)"
    return False, ""


def _swap_high(data, thresholds):
    swap = data.get("swap", {}).get("percent", 0)
    if swap > thresholds.swap_percent:
        return True, f"Swap usage at {swap:.1f}% (threshold: {thresholds.swap_percent}%)"
    return False, ""


def _gpu_temp_high(data, thresholds):
    temp = data.get("temperature", {}).get("current", 0)
    if temp > thresholds.gpu_temp_celsius:
        return True, f"GPU temperature at {temp}°C (threshold: {thresholds.gpu_temp_celsius}°C)"
    return False, ""


def _gpu_throttling(data, _thresholds):
    throttle = data.get("throttling", {})
    if throttle.get("active"):
        return True, f"GPU thermal throttling: {throttle.get('reason', 'unknown')}"
    return False, ""


def _disk_high(data, thresholds):
    for part in data.get("disk", {}).get("partitions", []):
        if part.get("percent", 0) > thresholds.disk_percent:
            return True, f"Disk {part['mountpoint']} at {part['percent']}% (threshold: {thresholds.disk_percent}%)"
    return False, ""


def _battery_low(data, thresholds):
    if not data.get("has_battery"):
        return False, ""
    cap = data.get("capacity", 100)
    status = data.get("status", "")
    if status == "Discharging" and cap < thresholds.battery_low_percent:
        return True, f"Battery at {cap}% — plug in soon!"
    return False, ""


def _battery_critical(data, thresholds):
    if not data.get("has_battery"):
        return False, ""
    cap = data.get("capacity", 100)
    status = data.get("status", "")
    if status == "Discharging" and cap < thresholds.battery_critical_percent:
        return True, f"CRITICAL: Battery at {cap}% — save your work!"
    return False, ""


def _zombie_processes(data, _thresholds):
    zombies = data.get("summary", {}).get("zombie", 0)
    if zombies > 2:  # 1-2 zombies is normal on most systems
        return True, f"{zombies} zombie processes detected"
    return False, ""


def _memory_leaks(data, _thresholds):
    leaks = data.get("summary", {}).get("leak_count", 0)
    if leaks > 0:
        return True, f"{leaks} process{'es' if leaks > 1 else ''} showing memory leak behavior"
    return False, ""


def _docker_oom(data, _thresholds):
    for c in data.get("containers", []):
        if "OOMKilled" in str(c.get("status", "")):
            return True, f"Container {c.get('name', '?')} was OOM killed"
    return False, ""


def _failed_services(data, _thresholds):
    failed = data.get("summary", {}).get("failed", 0)
    if failed > 0:
        return True, f"{failed} systemd service{'s' if failed > 1 else ''} in failed state"
    return False, ""


def _failed_logins(data, _thresholds):
    count = data.get("summary", {}).get("failed_login_count", 0)
    if count > 10:
        return True, f"{count} failed login attempts in the last 24 hours"
    return False, ""


DEFAULT_RULES = [
    AlertRule("CPU High", "CPU usage exceeds threshold", "warning", "system", True, _cpu_high),
    AlertRule("RAM High", "RAM usage exceeds threshold", "warning", "system", True, _ram_high),
    AlertRule("Swap High", "Swap usage exceeds threshold", "warning", "system", True, _swap_high),
    AlertRule("GPU Temp", "GPU temperature exceeds threshold", "warning", "gpu", True, _gpu_temp_high),
    AlertRule("GPU Throttling", "GPU is thermal throttling", "critical", "gpu", True, _gpu_throttling),
    AlertRule("Disk Full", "Disk usage exceeds threshold", "critical", "system", True, _disk_high),
    AlertRule("Battery Low", "Battery below low threshold", "warning", "battery", True, _battery_low),
    AlertRule("Battery Critical", "Battery critically low", "critical", "battery", True, _battery_critical),
    AlertRule("Zombie Processes", "Zombie processes detected", "info", "processes", True, _zombie_processes),
    AlertRule("Memory Leaks", "Processes with memory leak behavior", "warning", "processes", True, _memory_leaks),
    AlertRule("Docker OOM", "Container killed by OOM", "critical", "docker", True, _docker_oom),
    AlertRule("Failed Services", "systemd services in failed state", "warning", "services", True, _failed_services),
    AlertRule("Failed Logins", "Many failed login attempts", "warning", "security", True, _failed_logins),
]
