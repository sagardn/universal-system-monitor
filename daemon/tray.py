"""
Universal System Monitor — Tray Launcher

Starts the tray icon as a separate process.
If it crashes, the daemon is completely unaffected.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("usm.tray")


def start_tray_thread(shutdown_event=None):
    """Launch tray icon as a separate process (not a thread).

    This ensures any GTK/Wayland crash in the tray
    cannot bring down the daemon.
    """
    tray_script = Path(__file__).resolve().parent / "tray_app.py"

    if not tray_script.exists():
        logger.info("Tray app not found at %s", tray_script)
        return None

    try:
        proc = subprocess.Popen(
            ["/usr/bin/python3", str(tray_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Fully detached — daemon can't be killed by tray
        )
        logger.info("Tray icon process started (PID %d)", proc.pid)
        return proc
    except Exception as e:
        logger.info("Could not start tray: %s", e)
        return None
