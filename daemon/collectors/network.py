"""
Universal System Monitor — Network Collector

Monitors per-process network usage, active connections, bandwidth per
interface, and WiFi signal strength.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess

import psutil

from daemon.utils.sudo import has_passwordless_sudo

logger = logging.getLogger("usm.collectors.network")


class NetworkCollector:
    """Collects network connection and bandwidth data."""

    channel = "network"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.network

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
                logger.error("Network collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect network data."""
        connections = self._get_connections()
        interfaces = self._get_interfaces()
        per_process = self._get_per_process_bandwidth(connections)

        # Connection state summary
        state_counts = {}
        for conn in connections:
            state = conn.get("state", "UNKNOWN")
            state_counts[state] = state_counts.get(state, 0) + 1

        # Collect network service statuses
        services = self._get_service_statuses()

        return {
            "connections": connections[:200],  # Limit to 200 most relevant
            "interfaces": interfaces,
            "per_process_top": per_process[:20],  # Top 20 bandwidth consumers
            "state_summary": state_counts,
            "total_connections": len(connections),
            "services": services,
        }

    def _get_connections(self) -> list[dict]:
        """Get active network connections with process info."""
        connections = []
        try:
            for conn in psutil.net_connections(kind="inet"):
                laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
                raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""

                proc_name = ""
                if conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                connections.append({
                    "local": laddr,
                    "remote": raddr,
                    "state": conn.status,
                    "pid": conn.pid or 0,
                    "process": proc_name,
                    "family": "IPv4" if conn.family.name == "AF_INET" else "IPv6",
                    "type": "TCP" if conn.type.name == "SOCK_STREAM" else "UDP",
                })
        except (psutil.AccessDenied, PermissionError):
            # Try via ss command as fallback
            connections = self._get_connections_via_ss()

        return connections

    def _get_connections_via_ss(self) -> list[dict]:
        """Fallback: get connections via ss command."""
        try:
            result = subprocess.run(
                ["ss", "-tnpa"],
                capture_output=True, text=True, timeout=5,
            )
            connections = []
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 5:
                    state = parts[0]
                    local = parts[3] if len(parts) > 3 else ""
                    remote = parts[4] if len(parts) > 4 else ""

                    # Extract PID from users column
                    pid = 0
                    proc_name = ""
                    for p in parts[5:]:
                        pid_match = re.search(r'pid=(\d+)', p)
                        if pid_match:
                            pid = int(pid_match.group(1))
                        name_match = re.search(r'"([^"]+)"', p)
                        if name_match:
                            proc_name = name_match.group(1)

                    connections.append({
                        "local": local,
                        "remote": remote,
                        "state": state,
                        "pid": pid,
                        "process": proc_name,
                        "family": "IPv4",
                        "type": "TCP",
                    })
            return connections
        except Exception:
            return []

    def _get_interfaces(self) -> list[dict]:
        """Get network interface info."""
        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for name, addr_list in addrs.items():
            stat = stats.get(name)
            iface = {
                "name": name,
                "is_up": stat.isup if stat else False,
                "speed": stat.speed if stat else 0,
                "mtu": stat.mtu if stat else 0,
                "type": self._detect_iface_type(name),
                "addresses": [],
                "wifi_signal": None,
            }

            for addr in addr_list:
                if addr.family.name == "AF_INET":
                    iface["addresses"].append({
                        "family": "IPv4",
                        "address": addr.address,
                        "netmask": addr.netmask,
                    })
                elif addr.family.name == "AF_INET6":
                    iface["addresses"].append({
                        "family": "IPv6",
                        "address": addr.address,
                    })

            # WiFi signal strength
            if iface["type"] == "wifi":
                iface["wifi_signal"] = self._get_wifi_signal(name)

            interfaces.append(iface)

        return interfaces

    def _get_per_process_bandwidth(self, connections: list[dict]) -> list[dict]:
        """Estimate per-process bandwidth from connection count."""
        # Group connections by process
        proc_conns: dict[str, dict] = {}
        for conn in connections:
            if not conn["pid"]:
                continue
            key = f"{conn['pid']}:{conn['process']}"
            if key not in proc_conns:
                proc_conns[key] = {
                    "pid": conn["pid"],
                    "process": conn["process"],
                    "connections": 0,
                    "established": 0,
                    "listening": 0,
                }
            proc_conns[key]["connections"] += 1
            if conn["state"] == "ESTABLISHED":
                proc_conns[key]["established"] += 1
            elif conn["state"] == "LISTEN":
                proc_conns[key]["listening"] += 1

        # Sort by connection count
        result = sorted(proc_conns.values(), key=lambda x: x["connections"], reverse=True)
        return result

    @staticmethod
    def _detect_iface_type(name: str) -> str:
        """Detect interface type from name."""
        if name.startswith(("wl", "wlan")):
            return "wifi"
        elif name.startswith(("eth", "en")):
            return "ethernet"
        elif name.startswith(("tun", "tap", "wg")):
            return "vpn"
        elif name.startswith(("docker", "br-", "veth")):
            return "docker"
        elif name.startswith("virbr"):
            return "virtual"
        elif name == "lo":
            return "loopback"
        return "other"

    @staticmethod
    def _get_wifi_signal(interface: str) -> dict | None:
        """Get WiFi signal strength from /proc/net/wireless."""
        try:
            with open("/proc/net/wireless") as f:
                for line in f:
                    if interface in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            quality = float(parts[2].rstrip("."))
                            signal_dbm = float(parts[3].rstrip("."))
                            return {
                                "quality": quality,
                                "signal_dbm": signal_dbm,
                                "quality_percent": min(100, max(0, int((quality / 70) * 100))),
                            }
        except (OSError, ValueError):
            pass
        return None

    def _get_service_statuses(self) -> dict:
        """Collect status of network-related services."""
        services = {}

        # Tailscale
        if shutil.which("tailscale"):
            services["tailscale"] = self._get_tailscale_status()

        # WiFi (current connection via nmcli)
        if shutil.which("nmcli"):
            services["wifi"] = self._get_wifi_status()

        # Bluetooth
        if shutil.which("bluetoothctl"):
            services["bluetooth"] = self._get_bluetooth_status()

        # Firewall (UFW)
        if shutil.which("ufw"):
            services["firewall"] = self._get_firewall_status()

        # DNS
        if shutil.which("resolvectl"):
            services["dns"] = self._get_dns_status()

        return services

    @staticmethod
    def _get_tailscale_status() -> dict:
        """Get Tailscale connection status."""
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                self_node = data.get("Self", {})
                backend_state = data.get("BackendState", "")
                is_connected = backend_state == "Running"
                peers = data.get("Peer", {})
                online_peers = sum(1 for p in peers.values() if p.get("Online")) if is_connected else 0
                ips = self_node.get("TailscaleIPs", [])
                return {
                    "available": True,
                    "connected": is_connected,
                    "hostname": self_node.get("HostName", ""),
                    "ip": ips[0] if ips and is_connected else "",
                    "os": self_node.get("OS", ""),
                    "peers_total": len(peers),
                    "peers_online": online_peers,
                    "tailnet": data.get("MagicDNSSuffix", ""),
                }
        except Exception:
            pass
        return {"available": True, "connected": False, "hostname": "", "ip": "",
                "peers_total": 0, "peers_online": 0, "tailnet": ""}

    @staticmethod
    def _get_wifi_status() -> dict:
        """Get current WiFi connection status."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY,DEVICE", "device", "wifi", "list"],
                capture_output=True, text=True, timeout=5,
            )
            connected_ssid = ""
            signal = 0
            security = ""
            device = ""
            for line in result.stdout.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 5 and parts[0] == "yes":
                    connected_ssid = parts[1]
                    signal = int(parts[2]) if parts[2].isdigit() else 0
                    security = parts[3]
                    device = parts[4]
                    break
            return {
                "available": True,
                "connected": bool(connected_ssid),
                "ssid": connected_ssid,
                "signal": signal,
                "security": security,
                "device": device,
            }
        except Exception:
            pass
        return {"available": False, "connected": False, "ssid": "", "signal": 0}

    @staticmethod
    def _get_bluetooth_status() -> dict:
        """Get Bluetooth power status."""
        try:
            result = subprocess.run(
                ["bluetoothctl", "show"],
                capture_output=True, text=True, timeout=3,
            )
            powered = False
            name = ""
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Powered:"):
                    powered = "yes" in line.lower()
                elif line.startswith("Alias:") or line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
            return {"available": True, "powered": powered, "name": name}
        except Exception:
            pass
        return {"available": False, "powered": False, "name": ""}

    @staticmethod
    def _get_firewall_status() -> dict:
        """Get UFW firewall status."""
        if not has_passwordless_sudo():
            return {"available": False, "active": False, "rules": 0}
        try:
            result = subprocess.run(
                ["sudo", "-n", "ufw", "status"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                active = "Status: active" in output
                rules = sum(1 for line in output.split("\n") if line.strip() and not line.startswith("Status") and not line.startswith("To") and not line.startswith("--"))
                return {"available": True, "active": active, "rules": rules}
        except Exception:
            pass
        return {"available": True, "active": False, "rules": 0}

    @staticmethod
    def _get_dns_status() -> dict:
        """Get DNS resolver status."""
        try:
            result = subprocess.run(
                ["resolvectl", "status"],
                capture_output=True, text=True, timeout=3,
            )
            servers = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "DNS Servers:" in line or "Fallback DNS" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        for srv in parts[1].strip().split():
                            addr = srv.split("#")[0]  # Remove #comment
                            if addr and not addr.startswith("("):
                                servers.append(addr)
            return {"available": True, "servers": servers}
        except Exception:
            pass
        return {"available": False, "servers": []}

