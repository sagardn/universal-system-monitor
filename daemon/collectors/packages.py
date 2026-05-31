"""
Universal System Monitor — Package Update Collector

Multi-distro package update checker.
Supports: Arch (pacman), Debian/Ubuntu (apt), Fedora (dnf), openSUSE (zypper), Void (xbps), NixOS (nix).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess

from daemon.utils.sudo import has_passwordless_sudo

logger = logging.getLogger("usm.collectors.packages")


def detect_distro() -> str:
    """Detect the Linux distribution family."""
    try:
        with open("/etc/os-release") as f:
            content = f.read().lower()
        if any(x in content for x in ("arch", "cachyos", "manjaro", "endeavouros", "garuda")):
            return "arch"
        if any(x in content for x in ("ubuntu", "debian", "pop", "mint", "elementary", "zorin")):
            return "debian"
        if any(x in content for x in ("fedora", "rhel", "centos", "rocky", "alma")):
            return "fedora"
        if "opensuse" in content or "suse" in content:
            return "suse"
        if "void" in content:
            return "void"
        if "nixos" in content or "nix" in content:
            return "nix"
        if "gentoo" in content:
            return "gentoo"
    except OSError:
        pass

    # Fallback: check for package managers
    if shutil.which("pacman"):
        return "arch"
    if shutil.which("apt"):
        return "debian"
    if shutil.which("dnf"):
        return "fedora"
    if shutil.which("zypper"):
        return "suse"
    if shutil.which("xbps-query"):
        return "void"
    if shutil.which("nix"):
        return "nix"
    return "unknown"


class PackageCollector:
    """Checks for available package updates (multi-distro)."""

    channel = "packages"

    def __init__(self, config, ws_manager):
        self.config = config
        self.ws_manager = ws_manager
        self.interval = config.intervals.packages
        self.distro = detect_distro()
        self._backend = self._create_backend()
        logger.info("Package collector: detected distro=%s, backend=%s",
                     self.distro, self._backend.__class__.__name__)

    def _create_backend(self):
        backends = {
            "arch": ArchBackend,
            "debian": DebianBackend,
            "fedora": FedoraBackend,
            "suse": SuseBackend,
            "void": VoidBackend,
            "nix": NixBackend,
        }
        cls = backends.get(self.distro, GenericBackend)
        return cls()

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
                logger.error("Package collector error: %s", e)
            await asyncio.sleep(self.interval)

    def _collect(self) -> dict:
        """Collect package update information."""
        updates = self._backend.get_updates()
        installed_count = self._backend.get_installed_count()
        last_update = self._backend.get_last_update_time()
        pkg_manager = self._backend.name

        # Separate official vs third-party
        official = [u for u in updates if u.get("repo") != "aur"]
        aur = [u for u in updates if u.get("repo") == "aur"]

        return {
            "official_updates": official,
            "aur_updates": aur,
            "installed_count": installed_count,
            "last_update": last_update,
            "summary": {
                "official": len(official),
                "aur": len(aur),
                "total": len(updates),
            },
            "distro": self.distro,
            "package_manager": pkg_manager,
            "aur_helper": self._backend.aur_helper if hasattr(self._backend, "aur_helper") else "none",
        }


# ─── Distro Backends ─────────────────────────────────────────────────────────

class GenericBackend:
    name = "unknown"

    def get_updates(self) -> list[dict]:
        return []

    def get_installed_count(self) -> int:
        return 0

    def get_last_update_time(self) -> str:
        return ""


class ArchBackend(GenericBackend):
    """Arch Linux (pacman + paru/yay)."""
    name = "pacman"

    def __init__(self):
        self._checkupdates = shutil.which("checkupdates")
        self._paru = shutil.which("paru")
        self._yay = shutil.which("yay")
        self.aur_helper = "paru" if self._paru else "yay" if self._yay else "none"

    def get_updates(self) -> list[dict]:
        updates = self._get_official()
        updates.extend(self._get_aur())
        return updates

    def _get_official(self) -> list[dict]:
        if not self._checkupdates:
            return []
        try:
            result = subprocess.run(
                [self._checkupdates],
                capture_output=True, text=True, timeout=30,
            )
            updates = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    updates.append({
                        "name": parts[0], "current_version": parts[1],
                        "new_version": parts[3], "repo": "official",
                    })
            return updates
        except Exception as e:
            logger.debug("checkupdates failed: %s", e)
            return []

    def _get_aur(self) -> list[dict]:
        helper = self._paru or self._yay
        if not helper:
            return []
        try:
            result = subprocess.run(
                [helper, "-Qua"],
                capture_output=True, text=True, timeout=30,
            )
            updates = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    updates.append({
                        "name": parts[0], "current_version": parts[1],
                        "new_version": parts[3], "repo": "aur",
                    })
            return updates
        except Exception:
            return []

    def get_installed_count(self) -> int:
        try:
            result = subprocess.run(
                ["pacman", "-Q"], capture_output=True, text=True, timeout=10,
            )
            return len([l for l in result.stdout.strip().split("\n") if l])
        except Exception:
            return 0

    def get_last_update_time(self) -> str:
        try:
            log = "/var/log/pacman.log"
            if not os.path.exists(log):
                return ""
            result = subprocess.run(
                ["grep", "-i", "starting full system upgrade", log],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            if lines and lines[-1]:
                match = re.search(r'\[([^\]]+)\]', lines[-1])
                return match.group(1) if match else ""
        except Exception:
            pass
        return ""


class DebianBackend(GenericBackend):
    """Debian/Ubuntu (apt)."""
    name = "apt"

    def get_updates(self) -> list[dict]:
        try:
            # Update cache silently (needs passwordless sudo)
            if has_passwordless_sudo():
                subprocess.run(
                    ["sudo", "-n", "apt", "update"],
                    capture_output=True, timeout=60,
                )
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True, text=True, timeout=15,
                env={**os.environ, "LANG": "C"},
            )
            updates = []
            for line in result.stdout.strip().split("\n"):
                if "/" not in line or "Listing" in line:
                    continue
                # Format: package/source version arch [upgradable from: old_ver]
                match = re.match(r'^(\S+)/\S+\s+(\S+)\s+\S+\s+\[upgradable from:\s+(\S+)\]', line)
                if match:
                    updates.append({
                        "name": match.group(1), "new_version": match.group(2),
                        "current_version": match.group(3), "repo": "official",
                    })
            return updates
        except Exception as e:
            logger.debug("apt list failed: %s", e)
            return []

    def get_installed_count(self) -> int:
        try:
            result = subprocess.run(
                ["dpkg", "--list"], capture_output=True, text=True, timeout=10,
            )
            return sum(1 for l in result.stdout.split("\n") if l.startswith("ii"))
        except Exception:
            return 0

    def get_last_update_time(self) -> str:
        try:
            log = "/var/log/apt/history.log"
            if os.path.exists(log):
                result = subprocess.run(
                    ["grep", "Start-Date:", log],
                    capture_output=True, text=True, timeout=5,
                )
                lines = result.stdout.strip().split("\n")
                if lines and lines[-1]:
                    return lines[-1].replace("Start-Date:", "").strip()
        except Exception:
            pass
        return ""


class FedoraBackend(GenericBackend):
    """Fedora/RHEL (dnf)."""
    name = "dnf"

    def get_updates(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["dnf", "check-update", "--quiet"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "LANG": "C"},
            )
            # dnf check-update returns exit code 100 if updates available
            updates = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip() or line.startswith("Last metadata"):
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[0].rsplit(".", 1)[0]  # Remove arch suffix
                    updates.append({
                        "name": name, "new_version": parts[1],
                        "current_version": "", "repo": parts[2] if len(parts) > 2 else "official",
                    })
            return updates
        except Exception as e:
            logger.debug("dnf check-update failed: %s", e)
            return []

    def get_installed_count(self) -> int:
        try:
            result = subprocess.run(
                ["rpm", "-qa"], capture_output=True, text=True, timeout=10,
            )
            return len([l for l in result.stdout.strip().split("\n") if l])
        except Exception:
            return 0

    def get_last_update_time(self) -> str:
        try:
            result = subprocess.run(
                ["dnf", "history", "list", "--setopt=history_list_view=commands", "-q"],
                capture_output=True, text=True, timeout=10,
            )
            for line in reversed(result.stdout.strip().split("\n")):
                if "update" in line.lower() or "upgrade" in line.lower():
                    parts = line.split("|")
                    if len(parts) >= 3:
                        return parts[2].strip()
        except Exception:
            pass
        return ""


class SuseBackend(GenericBackend):
    """openSUSE (zypper)."""
    name = "zypper"

    def get_updates(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["zypper", "--non-interactive", "list-updates"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "LANG": "C"},
            )
            updates = []
            for line in result.stdout.strip().split("\n"):
                if "|" not in line or "----" in line or "Repository" in line or "S " in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    updates.append({
                        "name": parts[2], "current_version": parts[3],
                        "new_version": parts[4], "repo": parts[1],
                    })
            return updates
        except Exception as e:
            logger.debug("zypper list-updates failed: %s", e)
            return []

    def get_installed_count(self) -> int:
        try:
            result = subprocess.run(
                ["rpm", "-qa"], capture_output=True, text=True, timeout=10,
            )
            return len([l for l in result.stdout.strip().split("\n") if l])
        except Exception:
            return 0

    def get_last_update_time(self) -> str:
        try:
            log = "/var/log/zypp/history"
            if os.path.exists(log):
                result = subprocess.run(
                    ["tail", "-20", log],
                    capture_output=True, text=True, timeout=5,
                )
                for line in reversed(result.stdout.strip().split("\n")):
                    if line and not line.startswith("#"):
                        return line.split("|")[0].strip()
        except Exception:
            pass
        return ""


class VoidBackend(GenericBackend):
    """Void Linux (xbps)."""
    name = "xbps"

    def get_updates(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["xbps-install", "-Sun"],
                capture_output=True, text=True, timeout=60,
            )
            updates = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name_ver = parts[0].rsplit("-", 1)
                    updates.append({
                        "name": name_ver[0],
                        "new_version": name_ver[1] if len(name_ver) > 1 else "",
                        "current_version": "", "repo": "official",
                    })
            return updates
        except Exception:
            return []

    def get_installed_count(self) -> int:
        try:
            result = subprocess.run(
                ["xbps-query", "-l"], capture_output=True, text=True, timeout=10,
            )
            return len([l for l in result.stdout.strip().split("\n") if l])
        except Exception:
            return 0


class NixBackend(GenericBackend):
    """NixOS (nix)."""
    name = "nix"

    def get_updates(self) -> list[dict]:
        # NixOS doesn't have a simple "check updates" — would need channel comparison
        return []

    def get_installed_count(self) -> int:
        try:
            result = subprocess.run(
                ["nix-env", "-q"], capture_output=True, text=True, timeout=10,
            )
            return len([l for l in result.stdout.strip().split("\n") if l])
        except Exception:
            return 0
