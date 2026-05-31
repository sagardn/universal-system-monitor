#!/usr/bin/env python3
"""
Universal System Monitor — System Tray Icon (standalone process)

Runs as a SEPARATE process from the daemon.
If this crashes, the daemon is unaffected.
"""

import os
import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [usm.tray] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("usm.tray")

DASHBOARD_URL = "http://127.0.0.1:7777"

_ICON_PATHS = [
    Path(__file__).resolve().parent.parent / "assets" / "usm-icon.png",
    Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "usm.png",
    Path.home() / ".local" / "share" / "usm" / "assets" / "usm-icon.png",
]

_window_proc = None


def find_icon():
    for p in _ICON_PATHS:
        if p.exists():
            return str(p)
    return None


def open_window(*args):
    """Open native GTK WebKit window as a subprocess with X11 backend."""
    global _window_proc

    # Don't open multiple windows
    if _window_proc and _window_proc.poll() is None:
        return

    icon = find_icon() or ""

    viewer = Path(__file__).resolve().parent / "viewer.py"

    env = os.environ.copy()
    env["GDK_BACKEND"] = "x11"  # Force X11 — Wayland has protocol errors with WebKit
    env["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"

    _window_proc = subprocess.Popen(
        ["/usr/bin/python3", str(viewer), DASHBOARD_URL, icon],
        env=env,
        start_new_session=True,
    )
    logger.info("Window opened (PID %d)", _window_proc.pid)


def restart_service(*args):
    subprocess.Popen(["systemctl", "--user", "restart", "usm.service"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    import gi
    gi.require_version('Gtk', '3.0')

    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3 as AppIndicator
    except (ValueError, ImportError):
        gi.require_version('AyatanaAppIndicator3', '0.1')
        from gi.repository import AyatanaAppIndicator3 as AppIndicator

    from gi.repository import Gtk

    icon_path = find_icon()
    if not icon_path:
        logger.error("No icon found")
        sys.exit(1)

    indicator = AppIndicator.Indicator.new(
        "usm-monitor", icon_path,
        AppIndicator.IndicatorCategory.SYSTEM_SERVICES,
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    indicator.set_title("Universal System Monitor")
    indicator.set_icon_full(icon_path, "USM")

    menu = Gtk.Menu()

    item_open = Gtk.MenuItem(label="📊 Open Dashboard")
    item_open.connect("activate", open_window)
    menu.append(item_open)

    menu.append(Gtk.SeparatorMenuItem())

    item_restart = Gtk.MenuItem(label="🔄 Restart Service")
    item_restart.connect("activate", restart_service)
    menu.append(item_restart)

    item_quit = Gtk.MenuItem(label="❌ Quit")
    item_quit.connect("activate", lambda *a: Gtk.main_quit())
    menu.append(item_quit)

    menu.show_all()
    indicator.set_menu(menu)
    indicator.set_secondary_activate_target(item_open)

    logger.info("Tray icon ready")
    Gtk.main()


if __name__ == "__main__":
    main()
