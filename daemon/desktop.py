"""
Universal System Monitor — Desktop App

Starts the daemon server and opens a native desktop window
using pywebview (WebKitGTK on Linux).
"""

import os
import sys
import threading
import time
import socket
import logging
from pathlib import Path

logger = logging.getLogger("usm.desktop")

# Find icon relative to this file or from installed location
_ICON_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "assets" / "usm-icon.png",
    Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "usm.png",
    Path.home() / ".local" / "share" / "usm" / "assets" / "usm-icon.png",
]


def _find_icon() -> str | None:
    for p in _ICON_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def main():
    """Launch USM as a desktop app."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        import webview
    except ImportError:
        print("Error: pywebview not installed. Install with: uv pip install pywebview")
        sys.exit(1)

    # Start the daemon server in a background thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    _wait_for_server("127.0.0.1", 7777, timeout=15)

    # Find icon
    icon_path = _find_icon()
    if icon_path:
        logger.info("Using icon: %s", icon_path)

    # Create native window
    window = webview.create_window(
        title="Universal System Monitor",
        url="http://127.0.0.1:7777",
        width=1280,
        height=820,
        min_size=(900, 600),
        resizable=True,
        text_select=False,
        zoomable=True,
    )

    # Start the webview event loop (blocking)
    # Pass icon_path via settings
    webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False

    try:
        webview.start(debug=False, icon=icon_path)
    except TypeError:
        # Older pywebview versions don't support icon= parameter
        webview.start(debug=False)


def _start_server():
    """Start the USM aiohttp server in a background thread."""
    import asyncio
    from daemon.main import USMMonitor

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monitor = USMMonitor()
    try:
        loop.run_until_complete(monitor.start())
    except Exception as e:
        logger.error("Server error: %s", e)
    finally:
        loop.close()


def _wait_for_server(host: str, port: int, timeout: int = 15):
    """Wait until the server is accepting connections."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                logger.info("Server ready at http://%s:%d", host, port)
                return
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    print(f"Warning: Server not ready after {timeout}s, opening window anyway...")


if __name__ == "__main__":
    main()
