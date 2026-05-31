#!/usr/bin/env python3
"""
Universal System Monitor — Native Window Viewer

Opens a GTK+WebKit window showing the USM dashboard.
Must be run with GDK_BACKEND=x11 on Wayland systems.

Usage: GDK_BACKEND=x11 python3 viewer.py <url> [icon_path]
"""

import os
import sys

import gi
gi.require_version('Gtk', '3.0')

try:
    gi.require_version('WebKit2', '4.1')
except ValueError:
    gi.require_version('WebKit2', '4.0')

from gi.repository import Gtk, WebKit2, Gdk


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7777"
    icon_path = sys.argv[2] if len(sys.argv) > 2 else ""

    # Create window
    win = Gtk.Window(title="Universal System Monitor")
    win.set_default_size(1280, 820)
    win.set_position(Gtk.WindowPosition.CENTER)

    # Set window icon
    if icon_path and os.path.exists(icon_path):
        try:
            win.set_icon_from_file(icon_path)
        except Exception:
            pass

    # Create WebKit webview
    webview = WebKit2.WebView()
    settings = webview.get_settings()
    settings.set_property("enable-smooth-scrolling", True)
    settings.set_property("enable-developer-extras", False)

    # Dark background while loading
    try:
        bg = Gdk.RGBA()
        bg.red = 0.059
        bg.green = 0.09
        bg.blue = 0.165
        bg.alpha = 1.0
        webview.set_background_color(bg)
    except Exception:
        pass

    # Load the dashboard
    webview.load_uri(url)
    win.add(webview)

    # Close window = exit process
    win.connect("destroy", Gtk.main_quit)
    win.show_all()

    Gtk.main()


if __name__ == "__main__":
    main()
