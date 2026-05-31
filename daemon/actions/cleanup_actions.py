"""
Universal System Monitor — Cleanup Actions

Clean system junk: caches, trash, logs, temp files, orphan packages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("usm.actions.cleanup")


async def handle_cleanup_action(action: str, params: dict) -> dict:
    """Route cleanup actions."""
    handlers = {
        "clean_pacman": _clean_pacman,
        "clean_yay": _clean_aur_cache,
        "clean_paru": _clean_aur_cache,
        "clean_apt": _clean_apt,
        "clean_dnf": _clean_dnf,
        "clean_user_cache": _clean_user_cache,
        "clean_thumbnails": _clean_thumbnails,
        "clean_trash": _clean_trash,
        "clean_journal": _clean_journal,
        "clean_tmp": _clean_tmp,
        "clean_coredumps": _clean_coredumps,
        "clean_orphans": _clean_orphans,
        "clean_all": _clean_all,
    }

    handler = handlers.get(action)
    if not handler:
        return {"target": "cleanup", "action": action, "success": False,
                "message": f"Unknown action: {action}"}

    try:
        return await handler(params)
    except Exception as e:
        logger.exception("Cleanup action %s failed", action)
        return {"target": "cleanup", "action": action, "success": False,
                "message": str(e)}


def _fmt_size(b: int) -> str:
    """Human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for f in path.rglob("*"):
            try:
                if f.is_file() and not f.is_symlink():
                    total += f.stat().st_size
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass
    return total


async def _clean_pacman(params: dict) -> dict:
    """Clean pacman package cache (keep latest version only)."""
    # paccache is a bash script — run directly, not via python
    paccache = shutil.which("paccache")
    if paccache:
        proc = await asyncio.create_subprocess_exec(
            paccache, "-rk1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        msg = stdout.decode().strip() or stderr.decode().strip()
        return {"target": "cleanup", "action": "clean_pacman", "success": proc.returncode == 0,
                "message": f"✓ Pacman cache cleaned. {msg}" if proc.returncode == 0 else msg}

    # Fallback: pacman -Sc
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "pacman", "-Sc", "--noconfirm",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    return {"target": "cleanup", "action": "clean_pacman",
            "success": proc.returncode == 0,
            "message": "✓ Pacman cache cleaned" if proc.returncode == 0 else "Needs sudo"}


async def _clean_aur_cache(params: dict, _action: str = "") -> dict:
    """Clean AUR helper cache (yay or paru)."""
    home = Path.home()
    # Determine which helper from the action name
    helpers = ["yay", "paru"]

    cleaned = []
    for helper in helpers:
        cache_dir = home / ".cache" / helper
        if cache_dir.exists() and any(cache_dir.iterdir()):
            freed = _dir_size(cache_dir)
            def _do(d=cache_dir):
                shutil.rmtree(d, ignore_errors=True)
                d.mkdir(parents=True, exist_ok=True)
            await asyncio.get_event_loop().run_in_executor(None, _do)
            cleaned.append(f"{helper} ({_fmt_size(freed)})")

    if cleaned:
        return {"target": "cleanup", "action": "clean_aur", "success": True,
                "message": f"✓ AUR cache cleaned: {', '.join(cleaned)}"}
    return {"target": "cleanup", "action": "clean_aur", "success": True,
            "message": "AUR cache already clean"}


async def _clean_apt(params: dict) -> dict:
    """Clean APT package cache."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "apt-get", "clean",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.communicate(), timeout=15)
    return {"target": "cleanup", "action": "clean_apt",
            "success": proc.returncode == 0,
            "message": "✓ APT cache cleaned" if proc.returncode == 0 else "Needs sudo"}


async def _clean_dnf(params: dict) -> dict:
    """Clean DNF package cache."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "dnf", "clean", "all",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.communicate(), timeout=15)
    return {"target": "cleanup", "action": "clean_dnf",
            "success": proc.returncode == 0,
            "message": "✓ DNF cache cleaned" if proc.returncode == 0 else "Needs sudo"}


async def _clean_user_cache(params: dict) -> dict:
    """Clean user cache — removes non-critical cache dirs."""
    home = Path.home()
    cache_dir = home / ".cache"
    # Protect active caches
    protected = {"mesa_shader_cache", "fontconfig", "icon-cache.kcache", "chromium",
                 "google-chrome", "mozilla", "BraveSoftware", "Code", "pip"}

    freed = 0
    def _do():
        nonlocal freed
        for item in cache_dir.iterdir():
            if item.name in protected or item.name.startswith("."):
                continue
            try:
                s = _dir_size(item) if item.is_dir() else item.stat().st_size
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                freed += s
            except (OSError, PermissionError):
                pass

    await asyncio.get_event_loop().run_in_executor(None, _do)
    return {"target": "cleanup", "action": "clean_user_cache", "success": True,
            "message": f"✓ User cache cleaned ({_fmt_size(freed)})"}


async def _clean_thumbnails(params: dict) -> dict:
    """Clean thumbnail cache."""
    thumb_dir = Path.home() / ".cache" / "thumbnails"
    if not thumb_dir.exists():
        return {"target": "cleanup", "action": "clean_thumbnails", "success": True,
                "message": "No thumbnails to clean"}

    freed = _dir_size(thumb_dir)
    def _do():
        shutil.rmtree(thumb_dir, ignore_errors=True)
        thumb_dir.mkdir(parents=True, exist_ok=True)

    await asyncio.get_event_loop().run_in_executor(None, _do)
    return {"target": "cleanup", "action": "clean_thumbnails", "success": True,
            "message": f"✓ Thumbnails cleaned ({_fmt_size(freed)})"}


async def _clean_trash(params: dict) -> dict:
    """Empty trash."""
    trash_dir = Path.home() / ".local" / "share" / "Trash"
    if not trash_dir.exists():
        return {"target": "cleanup", "action": "clean_trash", "success": True,
                "message": "Trash already empty"}

    freed = _dir_size(trash_dir)
    def _do():
        for sub in ["files", "info", "expunged"]:
            d = trash_dir / sub
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                d.mkdir(parents=True, exist_ok=True)

    await asyncio.get_event_loop().run_in_executor(None, _do)
    return {"target": "cleanup", "action": "clean_trash", "success": True,
            "message": f"✓ Trash emptied ({_fmt_size(freed)})"}


async def _clean_journal(params: dict) -> dict:
    """Vacuum systemd journal logs to 100MB."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "journalctl", "--vacuum-size=100M",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    msg = stdout.decode().strip() or stderr.decode().strip()
    return {"target": "cleanup", "action": "clean_journal",
            "success": proc.returncode == 0,
            "message": f"✓ Journal vacuumed. {msg}" if proc.returncode == 0 else msg}


async def _clean_tmp(params: dict) -> dict:
    """Clean old files in /tmp (older than 3 days)."""
    proc = await asyncio.create_subprocess_exec(
        "find", "/tmp", "-type", "f", "-atime", "+3", "-delete",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.communicate(), timeout=15)
    return {"target": "cleanup", "action": "clean_tmp", "success": True,
            "message": "✓ Old temp files cleaned (3+ days old)"}


async def _clean_coredumps(params: dict) -> dict:
    """Remove old coredumps."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "find", "/var/lib/systemd/coredump", "-type", "f", "-delete",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.communicate(), timeout=10)
    return {"target": "cleanup", "action": "clean_coredumps",
            "success": proc.returncode == 0,
            "message": "✓ Core dumps cleaned" if proc.returncode == 0 else "Needs sudo"}


async def _clean_orphans(params: dict) -> dict:
    """Remove orphan packages (Arch only)."""
    # First get list
    proc = await asyncio.create_subprocess_exec(
        "pacman", "-Qdtq",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    pkgs = stdout.decode().strip()
    if not pkgs:
        return {"target": "cleanup", "action": "clean_orphans", "success": True,
                "message": "No orphan packages found"}

    # Remove them
    pkg_list = pkgs.split("\n")
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "pacman", "-Rns", "--noconfirm", *pkg_list,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    return {"target": "cleanup", "action": "clean_orphans",
            "success": proc.returncode == 0,
            "message": f"✓ Removed {len(pkg_list)} orphan packages" if proc.returncode == 0
                    else stderr.decode().strip() or "Needs sudo"}


async def _clean_all(params: dict) -> dict:
    """Run all safe cleanups."""
    results = []
    for handler in [_clean_thumbnails, _clean_trash, _clean_tmp]:
        try:
            r = await handler({})
            results.append(r.get("message", ""))
        except Exception:
            pass
    return {"target": "cleanup", "action": "clean_all", "success": True,
            "message": "✓ " + " | ".join(results)}
