"""
Universal System Monitor — Sudo Helper

Caches sudo availability. If `sudo -n` fails once (password required),
we skip all future sudo attempts to avoid spamming logs with
"a password is required" errors.
"""

import subprocess
import logging

logger = logging.getLogger("usm.sudo")

_sudo_available: bool | None = None  # None = untested


def has_passwordless_sudo() -> bool:
    """Check if passwordless sudo is available. Result is cached."""
    global _sudo_available
    if _sudo_available is not None:
        return _sudo_available

    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True, text=True, timeout=3,
        )
        _sudo_available = result.returncode == 0
    except Exception:
        _sudo_available = False

    if not _sudo_available:
        logger.info("Passwordless sudo not available — skipping privileged commands")
    return _sudo_available


def sudo_prefix() -> list[str]:
    """Return ['sudo', '-n'] if sudo is available, else []."""
    return ["sudo", "-n"] if has_passwordless_sudo() else []
