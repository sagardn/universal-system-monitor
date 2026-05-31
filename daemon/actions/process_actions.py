"""
Universal System Monitor — Process Actions

Send SIGTERM/SIGKILL to processes.
Includes system process protection and proper kill logic.
"""

import asyncio
import logging
import os
import signal
import subprocess

import psutil

logger = logging.getLogger("usm.actions.process")

# System-critical processes that should NEVER be killed
PROTECTED_PROCESSES = frozenset({
    'systemd', 'init', 'kthreadd', 'ksoftirqd', 'kworker',
    'rcu_sched', 'rcu_bh', 'migration', 'watchdog',
    'Xorg', 'Xwayland', 'sddm', 'gdm', 'lightdm',
    'dbus-daemon', 'dbus-broker', 'polkitd',
    'pipewire', 'pipewire-pulse', 'wireplumber',
    'NetworkManager', 'systemd-resolved', 'systemd-logind',
    'systemd-journald', 'systemd-udevd', 'systemd-timesyncd',
    'login', 'agetty', 'sshd', 'sudo',
    'kwin_wayland', 'kwin_x11', 'plasmashell', 'kded5', 'kded6',
    'gnome-shell', 'mutter',
})

# Processes where user should see a warning (not blocked, just warned)
WARN_PROCESSES = frozenset({
    'pulseaudio', 'bluetoothd', 'wpa_supplicant', 'avahi-daemon',
    'cups', 'cupsd', 'crond', 'cron', 'at-spi2-registryd',
    'gvfsd', 'udisksd', 'accounts-daemon', 'colord',
    'xdg-desktop-portal', 'xdg-permission-store',
    'baloo_file', 'tracker-miner-fs', 'gsd-',
})


def is_system_critical(name: str) -> bool:
    """Check if a process is system-critical."""
    name_lower = name.lower()
    return name in PROTECTED_PROCESSES or any(
        p.lower() in name_lower for p in PROTECTED_PROCESSES
    )


def is_warn_process(name: str) -> bool:
    """Check if a process should show a warning."""
    name_lower = name.lower()
    return any(w.lower() in name_lower for w in WARN_PROCESSES)


def get_process_safety(name: str) -> str:
    """Return safety level: 'critical', 'warn', or 'safe'."""
    if is_system_critical(name):
        return 'critical'
    if is_warn_process(name):
        return 'warn'
    return 'safe'


async def handle_process_action(action: str, params: dict) -> dict:
    """Handle process management actions."""
    pid = params.get("pid")
    if not pid:
        return {"target": "process", "action": action, "success": False,
                "message": "PID required"}

    pid = int(pid)

    if action in ("kill", "force_kill"):
        sig_name = "SIGKILL" if action == "force_kill" else params.get("signal", "SIGTERM")
        force_system = params.get("force", False)
        return await _kill_process(pid, sig_name, force_system)
    elif action == "check_safety":
        return await _check_safety(pid)
    else:
        return {"target": "process", "action": action, "success": False,
                "message": f"Unknown action: {action}"}


async def _check_safety(pid: int) -> dict:
    """Check if a process is safe to kill."""
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        safety = get_process_safety(name)
        return {
            "target": "process", "action": "check_safety", "success": True,
            "data": {"pid": pid, "name": name, "safety": safety}
        }
    except psutil.NoSuchProcess:
        return {"target": "process", "action": "check_safety", "success": False,
                "message": f"Process {pid} not found"}


async def _kill_process(pid: int, sig_name: str, force_system: bool = False) -> dict:
    """Send a signal to a process."""
    sig = signal.SIGTERM if sig_name == "SIGTERM" else signal.SIGKILL

    # Check if process exists
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()
        proc_user = proc.username()
    except psutil.NoSuchProcess:
        return {"target": "process", "action": "kill", "success": False,
                "message": f"Process {pid} not found"}

    # Block system-critical processes
    if is_system_critical(proc_name) and not force_system:
        return {"target": "process", "action": "kill", "success": False,
                "message": f"⛔ {proc_name} is a system-critical process and cannot be killed. "
                           f"Killing it would crash your system."}

    # Check ownership
    current_user = os.environ.get("USER", "")
    is_own_process = (proc_user == current_user)

    # Try direct kill first (for user-owned processes)
    if is_own_process:
        try:
            os.kill(pid, sig)
            # Wait briefly and verify
            await asyncio.sleep(0.3)
            if not psutil.pid_exists(pid):
                logger.info("Killed process %d (%s) with %s", pid, proc_name, sig_name)
                return {"target": "process", "action": "kill", "success": True,
                        "message": f"✓ Sent {sig_name} to {proc_name} (PID {pid})"}
            else:
                # Process still alive after SIGTERM - it may be handling the signal
                if sig == signal.SIGTERM:
                    return {"target": "process", "action": "kill", "success": True,
                            "message": f"Sent {sig_name} to {proc_name} (PID {pid}). "
                                       f"Process is shutting down gracefully."}
                else:
                    return {"target": "process", "action": "kill", "success": False,
                            "message": f"Process {proc_name} ({pid}) did not die after SIGKILL"}
        except ProcessLookupError:
            return {"target": "process", "action": "kill", "success": True,
                    "message": f"✓ Process {proc_name} (PID {pid}) already terminated"}
        except PermissionError:
            pass  # Fall through to elevated kill

    # Need elevated privileges — use kill command via pkexec
    try:
        sig_num = "15" if sig == signal.SIGTERM else "9"
        result = await asyncio.create_subprocess_exec(
            "pkexec", "kill", f"-{sig_num}", str(pid),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=30)

        if result.returncode == 0:
            logger.info("Killed process %d (%s) with %s via pkexec", pid, proc_name, sig_name)
            return {"target": "process", "action": "kill", "success": True,
                    "message": f"✓ Sent {sig_name} to {proc_name} (PID {pid}) [elevated]"}
        elif result.returncode == 126:
            return {"target": "process", "action": "kill", "success": False,
                    "message": "Authentication cancelled by user"}
        else:
            err = stderr.decode().strip()
            return {"target": "process", "action": "kill", "success": False,
                    "message": f"Kill failed: {err or 'Unknown error'}"}

    except asyncio.TimeoutError:
        return {"target": "process", "action": "kill", "success": False,
                "message": "Authentication timed out (30s)"}
    except FileNotFoundError:
        # pkexec not available, try sudo as fallback
        try:
            result = await asyncio.create_subprocess_exec(
                "sudo", "-n", "kill", f"-{sig_num}", str(pid),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            if result.returncode == 0:
                return {"target": "process", "action": "kill", "success": True,
                        "message": f"✓ Sent {sig_name} to {proc_name} (PID {pid}) [sudo]"}
            return {"target": "process", "action": "kill", "success": False,
                    "message": f"Needs elevated privileges to kill {proc_name} (owned by {proc_user})"}
        except Exception:
            return {"target": "process", "action": "kill", "success": False,
                    "message": f"Cannot kill {proc_name} — owned by {proc_user}, "
                               f"and no privilege escalation available"}
    except Exception as e:
        return {"target": "process", "action": "kill", "success": False,
                "message": f"Error: {str(e)}"}
