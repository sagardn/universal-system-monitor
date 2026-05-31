"""
Universal System Monitor — Security Collector

Monitors failed login attempts (SSH/sudo), open listening ports,
firewall status, and recent security events.
"""

from __future__ import annotations

import asyncio
import logging
import json
import re
import subprocess

logger = logging.getLogger("usm.collectors.security")


class SecurityCollector:
    """Collects security-related system data."""

    channel = "security"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.security

    async def run(self):
        """Main collector loop."""
        while True:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self._collect
                )
                await self.ws_manager.broadcast(self.channel, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Security collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect security data."""
        failed_logins = self._get_failed_logins()
        open_ports = self._get_open_ports()
        firewall = self._get_firewall_status()

        # Calculate security score
        score = self._calculate_score(failed_logins, open_ports, firewall)

        return {
            "failed_logins": failed_logins[:50],
            "open_ports": open_ports,
            "firewall": firewall,
            "security_score": score,
            "summary": {
                "failed_login_count": len(failed_logins),
                "open_port_count": len(open_ports),
                "firewall_active": firewall.get("active", False),
            },
        }

    def _get_failed_logins(self) -> list[dict]:
        """Parse journalctl for failed authentication attempts."""
        events = []

        # SSH failures
        try:
            result = subprocess.run(
                ["journalctl", "-u", "sshd", "--no-pager", "-n", "200",
                 "--output=json", "--since", "24 hours ago"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    msg = entry.get("MESSAGE", "")
                    if "Failed" in msg or "authentication failure" in msg.lower():
                        # Extract IP and username
                        ip_match = re.search(r'from\s+([\d.]+|[a-f\d:]+)', msg)
                        user_match = re.search(r'(?:user|for)\s+(\S+)', msg)
                        events.append({
                            "timestamp": entry.get("__REALTIME_TIMESTAMP", ""),
                            "service": "ssh",
                            "message": msg[:200],
                            "ip": ip_match.group(1) if ip_match else "",
                            "username": user_match.group(1) if user_match else "",
                            "severity": "warning",
                        })
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass

        # sudo failures
        try:
            result = subprocess.run(
                ["journalctl", "_COMM=sudo", "--no-pager", "-n", "100",
                 "--output=json", "--since", "24 hours ago"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    msg = entry.get("MESSAGE", "")
                    if "incorrect password" in msg.lower() or "NOT in sudoers" in msg:
                        user_match = re.search(r'(\S+)\s*:', msg)
                        events.append({
                            "timestamp": entry.get("__REALTIME_TIMESTAMP", ""),
                            "service": "sudo",
                            "message": msg[:200],
                            "ip": "localhost",
                            "username": user_match.group(1) if user_match else "",
                            "severity": "critical" if "NOT in sudoers" in msg else "warning",
                        })
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass

        # Sort by timestamp descending
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events

    def _get_open_ports(self) -> list[dict]:
        """Get listening ports and their processes."""
        ports = []
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) < 5:
                    continue

                local_addr = parts[3]
                # Extract port
                port_match = re.search(r':(\d+)$', local_addr)
                port = int(port_match.group(1)) if port_match else 0

                # Extract bind address
                bind = local_addr.rsplit(":", 1)[0] if ":" in local_addr else "*"

                # Extract process info
                pid = 0
                proc_name = ""
                for p in parts:
                    pid_match = re.search(r'pid=(\d+)', p)
                    if pid_match:
                        pid = int(pid_match.group(1))
                    name_match = re.search(r'"([^"]+)"', p)
                    if name_match:
                        proc_name = name_match.group(1)

                # Known service detection
                known_services = {
                    22: "SSH", 80: "HTTP", 443: "HTTPS", 3000: "Dev Server",
                    3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis",
                    27017: "MongoDB", 8080: "HTTP Alt", 8443: "HTTPS Alt",
                    53: "DNS", 631: "CUPS", 5353: "mDNS",
                }

                ports.append({
                    "port": port,
                    "protocol": "TCP",
                    "bind": bind,
                    "pid": pid,
                    "process": proc_name,
                    "known_service": known_services.get(port, ""),
                    "is_expected": port in known_services,
                })

            # Sort by port number
            ports.sort(key=lambda p: p["port"])

        except Exception as e:
            logger.debug("ss command failed: %s", e)

        return ports

    def _get_firewall_status(self) -> dict:
        """Detect and report firewall status."""
        # Try nftables
        try:
            result = subprocess.run(
                ["nft", "list", "ruleset"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                rules = result.stdout.strip()
                rule_count = rules.count("\n") if rules else 0
                return {
                    "type": "nftables",
                    "active": bool(rules.strip()),
                    "rule_count": rule_count,
                    "default_policy": self._detect_nft_policy(rules),
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Try iptables
        try:
            result = subprocess.run(
                ["iptables", "-L", "-n", "--line-numbers"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                rule_count = sum(1 for l in lines if l and not l.startswith(("Chain", "num")))
                # Detect default policy
                policy = "ACCEPT"
                for line in lines:
                    if line.startswith("Chain INPUT"):
                        match = re.search(r'policy\s+(\w+)', line)
                        if match:
                            policy = match.group(1)
                            break
                return {
                    "type": "iptables",
                    "active": rule_count > 0,
                    "rule_count": rule_count,
                    "default_policy": policy,
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Try firewalld
        try:
            result = subprocess.run(
                ["firewall-cmd", "--state"],
                capture_output=True, text=True, timeout=5,
            )
            running = "running" in result.stdout.lower()
            return {
                "type": "firewalld",
                "active": running,
                "rule_count": 0,
                "default_policy": "varies",
            }
        except FileNotFoundError:
            pass
        except Exception:
            pass

        return {"type": "none", "active": False, "rule_count": 0, "default_policy": "none"}

    @staticmethod
    def _detect_nft_policy(ruleset: str) -> str:
        """Detect default policy from nftables ruleset."""
        match = re.search(r'chain\s+input\s*\{[^}]*policy\s+(\w+)', ruleset, re.IGNORECASE)
        return match.group(1) if match else "accept"

    @staticmethod
    def _calculate_score(failed_logins, open_ports, firewall) -> dict:
        """Calculate a simple security score."""
        score = 100
        issues = []

        # Firewall
        if not firewall.get("active"):
            score -= 30
            issues.append("No active firewall detected")

        # Failed logins
        login_count = len(failed_logins)
        if login_count > 50:
            score -= 25
            issues.append(f"{login_count} failed login attempts in 24h")
        elif login_count > 10:
            score -= 15
            issues.append(f"{login_count} failed login attempts in 24h")
        elif login_count > 0:
            score -= 5

        # Open ports
        unexpected = [p for p in open_ports if not p["is_expected"]]
        if len(unexpected) > 5:
            score -= 15
            issues.append(f"{len(unexpected)} unexpected open ports")
        elif len(unexpected) > 0:
            score -= 5

        # SSH on default port
        ssh_default = any(p["port"] == 22 for p in open_ports)
        if ssh_default:
            score -= 5
            issues.append("SSH on default port 22")

        score = max(0, score)
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

        return {
            "score": score,
            "grade": grade,
            "issues": issues,
        }
