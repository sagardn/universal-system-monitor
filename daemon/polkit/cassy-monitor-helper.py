#!/usr/bin/env python3
"""
Universal System Monitor — Polkit Helper

Standalone script invoked via pkexec for privileged operations.
Accepts a JSON argument with action details and executes them.

Usage: pkexec python3 usm-helper.py '{"action":"kill","pid":1234,"signal":"SIGTERM"}'
"""

import json
import os
import signal
import subprocess
import sys


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    action = args.get("action")

    if action == "kill":
        pid = args.get("pid")
        sig_name = args.get("signal", "SIGTERM")
        if not pid:
            print(json.dumps({"error": "PID required"}))
            sys.exit(1)

        sig = signal.SIGTERM if sig_name == "SIGTERM" else signal.SIGKILL
        try:
            os.kill(int(pid), sig)
            print(json.dumps({"success": True, "message": f"Sent {sig_name} to PID {pid}"}))
        except ProcessLookupError:
            print(json.dumps({"error": f"Process {pid} not found"}))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

    elif action == "service":
        name = args.get("name")
        operation = args.get("operation")
        if not name or not operation:
            print(json.dumps({"error": "name and operation required"}))
            sys.exit(1)

        if operation not in ("start", "stop", "restart", "enable", "disable", "reload"):
            print(json.dumps({"error": f"Invalid operation: {operation}"}))
            sys.exit(1)

        try:
            result = subprocess.run(
                ["systemctl", operation, name],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                print(json.dumps({"success": True, "message": f"{name} {operation}ed"}))
            else:
                print(json.dumps({"error": result.stderr.strip()}))
                sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
