"""
Universal System Monitor — Icon Resolver

Maps process names to .desktop file icons. Scans /usr/share/applications/
and ~/.local/share/applications/ for Exec→Icon mappings, then resolves
icon names to actual file paths via the icon theme hierarchy.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from configparser import ConfigParser

logger = logging.getLogger("usm.collectors.icons")

DESKTOP_DIRS = [
    Path("/usr/share/applications"),
    Path.home() / ".local" / "share" / "applications",
]

ICON_THEME_DIRS = [
    Path.home() / ".local" / "share" / "icons",
    Path("/usr/share/icons/hicolor"),
    Path("/usr/share/icons"),
    Path("/usr/share/pixmaps"),
]

ICON_SIZES = ["48x48", "64x64", "32x32", "scalable", "256x256", "128x128", "96x96"]
ICON_EXTENSIONS = [".svg", ".png", ".xpm"]
ICON_CATEGORIES = ["apps", "applications"]


class IconResolver:
    """Resolves process executable names to icon file paths."""

    def __init__(self):
        # exec_basename -> icon_file_path
        self._cache: dict[str, str] = {}
        # icon_name -> icon_file_path (intermediate cache)
        self._icon_path_cache: dict[str, str] = {}

    def build_cache(self):
        """Scan .desktop files and build the exec→icon mapping."""
        self._cache.clear()
        self._icon_path_cache.clear()

        exec_to_icon_name: dict[str, str] = {}

        for desktop_dir in DESKTOP_DIRS:
            if not desktop_dir.is_dir():
                continue
            for desktop_file in desktop_dir.glob("*.desktop"):
                try:
                    self._parse_desktop_file(desktop_file, exec_to_icon_name)
                except Exception as e:
                    logger.debug("Failed to parse %s: %s", desktop_file, e)

        # Resolve icon names to file paths
        for exec_name, icon_name in exec_to_icon_name.items():
            icon_path = self._resolve_icon_path(icon_name)
            if icon_path:
                self._cache[exec_name] = icon_path

        logger.info("Icon cache: %d exec→icon mappings", len(self._cache))

    def _parse_desktop_file(self, path: Path, mapping: dict):
        """Extract Exec and Icon from a .desktop file."""
        parser = ConfigParser(interpolation=None, strict=False)
        parser.read(str(path), encoding="utf-8")

        if not parser.has_section("Desktop Entry"):
            return

        exec_val = parser.get("Desktop Entry", "Exec", fallback=None)
        icon_val = parser.get("Desktop Entry", "Icon", fallback=None)

        if not exec_val or not icon_val:
            return

        # Extract the executable basename from Exec=
        # Exec can be like: /usr/bin/foo --bar %u
        exec_cmd = exec_val.split()[0]
        exec_basename = os.path.basename(exec_cmd)

        # Remove common wrappers
        if exec_basename in ("env", "bash", "sh", "python", "python3"):
            parts = exec_val.split()
            for part in parts[1:]:
                if not part.startswith("-") and not "=" in part:
                    exec_basename = os.path.basename(part)
                    break

        if exec_basename and icon_val:
            mapping[exec_basename] = icon_val
            # Also map without common suffixes
            for suffix in ("-bin", "-wrapped"):
                if exec_basename.endswith(suffix):
                    mapping[exec_basename[:-len(suffix)]] = icon_val

    def _resolve_icon_path(self, icon_name: str) -> str | None:
        """Resolve an icon name to an actual file path."""
        if icon_name in self._icon_path_cache:
            return self._icon_path_cache[icon_name]

        # If icon_name is already an absolute path
        if os.path.isabs(icon_name) and os.path.isfile(icon_name):
            self._icon_path_cache[icon_name] = icon_name
            return icon_name

        # Search through icon theme directories
        for theme_dir in ICON_THEME_DIRS:
            if not theme_dir.is_dir():
                continue

            # Try size/category directories (e.g., /usr/share/icons/hicolor/48x48/apps/)
            for size in ICON_SIZES:
                for category in ICON_CATEGORIES:
                    base = theme_dir / size / category
                    if not base.is_dir():
                        continue
                    for ext in ICON_EXTENSIONS:
                        candidate = base / f"{icon_name}{ext}"
                        if candidate.is_file():
                            resolved = str(candidate)
                            self._icon_path_cache[icon_name] = resolved
                            return resolved

            # Try directly in the directory (e.g., /usr/share/pixmaps/)
            for ext in ICON_EXTENSIONS:
                candidate = theme_dir / f"{icon_name}{ext}"
                if candidate.is_file():
                    resolved = str(candidate)
                    self._icon_path_cache[icon_name] = resolved
                    return resolved

        return None

    def resolve(self, process_name: str) -> str | None:
        """Get the icon file path for a process name."""
        # Direct match
        if process_name in self._cache:
            return self._cache[process_name]

        # Try lowercase
        lower = process_name.lower()
        if lower in self._cache:
            return self._cache[lower]

        # Try common variations
        for variant in [lower, lower.replace("-", ""), lower.split("-")[0]]:
            if variant in self._cache:
                return self._cache[variant]

        return None

    def has_icon(self, process_name: str) -> bool:
        """Check if an icon exists for a process name."""
        return self.resolve(process_name) is not None
