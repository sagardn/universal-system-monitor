"""
Universal System Monitor — Cron Actions

Add, edit, delete, and toggle cron jobs.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess

logger = logging.getLogger("usm.actions.cron")


async def handle_cron_action(action: str, params: dict) -> dict:
    """Route cron actions."""
    handlers = {
        "add": _add_job,
        "delete": _delete_job,
        "toggle": _toggle_job,
    }

    handler = handlers.get(action)
    if not handler:
        return {"target": "cron", "action": action, "success": False,
                "message": f"Unknown action: {action}"}

    try:
        return await handler(params)
    except Exception as e:
        logger.exception("Cron action %s failed", action)
        return {"target": "cron", "action": action, "success": False,
                "message": str(e)}


def _get_crontab() -> list[str]:
    """Read current user crontab as lines."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")
    except Exception:
        pass
    return []


def _set_crontab(lines: list[str]) -> tuple[bool, str]:
    """Write user crontab from lines."""
    content = "\n".join(lines) + "\n"
    try:
        result = subprocess.run(
            ["crontab", "-"],
            input=content, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)


async def _add_job(params: dict) -> dict:
    """Add a new cron job."""
    schedule = params.get("schedule", "").strip()
    command = params.get("command", "").strip()

    if not schedule or not command:
        return {"target": "cron", "action": "add", "success": False,
                "message": "Schedule and command are required"}

    new_line = f"{schedule} {command}"

    def _do():
        lines = _get_crontab()
        # Don't add if already exists
        if new_line in lines:
            return False, "Job already exists"
        lines.append(new_line)
        return _set_crontab(lines)

    ok, msg = await asyncio.get_event_loop().run_in_executor(None, _do)

    return {"target": "cron", "action": "add", "success": ok,
            "message": msg or f"✓ Added: {new_line}"}


async def _delete_job(params: dict) -> dict:
    """Delete a cron job by its raw line content."""
    raw = params.get("raw", "").strip()
    if not raw:
        return {"target": "cron", "action": "delete", "success": False,
                "message": "Raw line content required"}

    def _do():
        lines = _get_crontab()
        # Remove the line (and its commented version)
        new_lines = [l for l in lines if l.strip() != raw and l.strip() != f"# {raw}"]
        if len(new_lines) == len(lines):
            return False, "Job not found"
        return _set_crontab(new_lines)

    ok, msg = await asyncio.get_event_loop().run_in_executor(None, _do)

    return {"target": "cron", "action": "delete", "success": ok,
            "message": msg or "✓ Job deleted"}


async def _toggle_job(params: dict) -> dict:
    """Enable/disable a cron job by commenting/uncommenting."""
    raw = params.get("raw", "").strip()
    enable = params.get("enable", True)

    if not raw:
        return {"target": "cron", "action": "toggle", "success": False,
                "message": "Raw line content required"}

    def _do():
        lines = _get_crontab()
        new_lines = []
        found = False
        for line in lines:
            stripped = line.strip()
            if enable and stripped == f"# {raw}":
                new_lines.append(raw)
                found = True
            elif not enable and stripped == raw:
                new_lines.append(f"# {raw}")
                found = True
            else:
                new_lines.append(line)

        if not found:
            return False, "Job not found in crontab"
        return _set_crontab(new_lines)

    ok, msg = await asyncio.get_event_loop().run_in_executor(None, _do)

    state = "enabled" if enable else "disabled"
    return {"target": "cron", "action": "toggle", "success": ok,
            "message": msg or f"✓ Job {state}"}
