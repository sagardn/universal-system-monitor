"""
Universal System Monitor — Speed Test Actions

Run network speed tests using speedtest-cli or curl fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time

logger = logging.getLogger("usm.actions.speedtest")


async def handle_speedtest_action(action: str, params: dict) -> dict:
    """Route speedtest actions."""
    if action == "run":
        return await _run_speedtest(params)
    return {"target": "speedtest", "action": action, "success": False,
            "message": f"Unknown action: {action}"}


async def _run_speedtest(params: dict) -> dict:
    """Run a speed test. Tries speedtest-cli first, falls back to curl."""
    try:
        # Try speedtest-cli (python package or system binary)
        if shutil.which("speedtest-cli") or shutil.which("speedtest"):
            return await _speedtest_cli()
        else:
            return await _curl_speedtest()
    except Exception as e:
        logger.exception("Speed test failed")
        return {"target": "speedtest", "action": "run", "success": False,
                "message": str(e)}


async def _speedtest_cli() -> dict:
    """Run speedtest-cli and parse JSON output."""
    cmd = "speedtest-cli" if shutil.which("speedtest-cli") else "speedtest"

    proc = await asyncio.create_subprocess_exec(
        cmd, "--json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

    if proc.returncode != 0:
        return {"target": "speedtest", "action": "run", "success": False,
                "message": stderr.decode().strip() or "speedtest-cli failed"}

    data = json.loads(stdout.decode())

    return {
        "target": "speedtest", "action": "run", "success": True,
        "data": {
            "download": round(data.get("download", 0) / 1_000_000, 2),  # Mbps
            "upload": round(data.get("upload", 0) / 1_000_000, 2),
            "ping": round(data.get("ping", 0), 1),
            "server": data.get("server", {}).get("sponsor", "Unknown"),
            "server_location": data.get("server", {}).get("name", ""),
            "isp": data.get("client", {}).get("isp", ""),
            "ip": data.get("client", {}).get("ip", ""),
            "timestamp": data.get("timestamp", ""),
        },
    }


async def _curl_speedtest() -> dict:
    """Fallback: measure download speed with curl to a CDN."""
    url = "https://speed.cloudflare.com/__down?bytes=10000000"  # 10MB
    start = time.monotonic()

    proc = await asyncio.create_subprocess_exec(
        "curl", "-o", "/dev/null", "-s", "-w", "%{speed_download},%{time_total},%{remote_ip}",
        "--max-time", "15", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
    elapsed = time.monotonic() - start

    parts = stdout.decode().strip().split(",")
    if len(parts) >= 2:
        speed_bps = float(parts[0])  # bytes/sec
        speed_mbps = round(speed_bps * 8 / 1_000_000, 2)
        return {
            "target": "speedtest", "action": "run", "success": True,
            "data": {
                "download": speed_mbps,
                "upload": 0,  # curl fallback doesn't test upload
                "ping": round(float(parts[1]) * 1000, 1) if len(parts) >= 2 else 0,
                "server": "Cloudflare CDN",
                "server_location": "",
                "isp": "",
                "ip": parts[2] if len(parts) >= 3 else "",
                "timestamp": "",
                "fallback": True,
            },
        }

    return {"target": "speedtest", "action": "run", "success": False,
            "message": "Could not measure speed. Install speedtest-cli for better results."}
