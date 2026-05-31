<p align="center">
  <img src="assets/usm-icon.png" width="128" height="128" alt="USM Icon">
</p>

<h1 align="center">Universal System Monitor</h1>

<p align="center">
  <strong>A real-time Linux system monitor with a premium web dashboard, system tray icon, and native desktop window.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-blue?style=flat-square" alt="Linux">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="MIT">
  <img src="https://img.shields.io/badge/version-0.2.0-cyan?style=flat-square" alt="v0.2.0">
</p>

---

## ✨ Features

| Category | What it monitors |
|----------|-----------------|
| 🖥️ **System** | CPU, RAM, swap, uptime, load average |
| 🎮 **GPU** | NVIDIA/AMD — temp, usage, VRAM, fan speed |
| 🌡️ **Thermal** | All temperature sensors, fan RPM |
| 🔋 **Battery** | Charge level, time remaining, power profiles |
| 💾 **Disks** | SMART health, SSD lifespan, NVMe stats |
| 🌐 **Network** | Per-interface bandwidth, WiFi signal, firewall |
| 🐳 **Docker** | Container status, CPU/memory per container |
| ⚙️ **Services** | Systemd service management (start/stop/restart) |
| 📦 **Packages** | Available updates (pacman/apt/dnf/zypper) |
| 🔊 **Audio** | PipeWire/WirePlumber volume control, mute toggle |
| 🔒 **Security** | Failed SSH/sudo attempts, open ports, firewall |
| 📸 **Snapshots** | Btrfs snapshot management |
| 🧹 **Cleanup** | Pacman cache, orphans, journal, core dumps |
| ⏰ **Cron** | Cron job viewer |
| 🚀 **Startup** | Boot service manager |
| 📊 **Processes** | Process list with kill/signal/priority control |
| 🔔 **Alerts** | CPU/RAM/temp threshold alerts |

### Desktop Integration

- **System Tray Icon** — Always visible next to network/sound icons
- **Native Window** — Click tray → opens GTK+WebKit window (not Chrome)
- **Auto-start** — Starts on login via systemd user service
- **Crash-proof** — Tray/window run as separate processes

---

## 📸 Screenshots

> Run `usm` and open `http://127.0.0.1:7777` to see the dashboard.

---

## 🚀 Quick Install (Any Linux)

```bash
git clone https://github.com/sagardn/universal-system-monitor.git
cd universal-system-monitor
bash install.sh
```

**That's it!** USM will start automatically. Access dashboard at **http://127.0.0.1:7777**

---

## 📋 Detailed Installation

### Prerequisites

| Requirement | How to check | Install |
|-------------|-------------|---------|
| **Python 3.10+** | `python3 --version` | Usually pre-installed |
| **Node.js/Bun** | `bun --version` or `node --version` | For building frontend |
| **GTK3** | `python3 -c "import gi"` | Usually pre-installed |
| **AppIndicator3** | System tray support | Usually pre-installed |
| **WebKitGTK** | Native window support | Usually pre-installed |

### Step 1: Clone the repository

```bash
git clone https://github.com/sagardn/universal-system-monitor.git
cd universal-system-monitor
```

### Step 2: Build the frontend

```bash
cd frontend
bun install    # or: npm install
bun run build  # or: npm run build
cd ..
```

### Step 3: Run the installer

```bash
bash install.sh
```

The installer will:
- Copy files to `~/.local/share/usm/`
- Create a Python virtual environment
- Install Python dependencies
- Create `usm` command in `~/.local/bin/`
- Set up a **systemd user service** (auto-starts on login)
- Add a **desktop entry** (searchable in app launcher)
- Install the **app icon**
- Start the service immediately

### Step 4: Verify

```bash
# Check service is running
systemctl --user status usm

# Open dashboard
xdg-open http://127.0.0.1:7777
```

---

## 🏗️ Installation by Distro

### Arch Linux / CachyOS / Manjaro

```bash
# Install dependencies
sudo pacman -S python python-psutil python-aiohttp python-pillow python-aiosqlite \
    webkit2gtk libappindicator-gtk3 wireplumber

# Clone and install
git clone https://github.com/sagardn/universal-system-monitor.git
cd universal-system-monitor
bash install.sh
```

**Or build a native package:**

```bash
cd universal-system-monitor
makepkg -si
```

### Ubuntu / Debian

```bash
# Install dependencies
sudo apt install python3 python3-venv python3-pip python3-psutil \
    python3-aiohttp python3-pil gir1.2-webkit2-4.1 gir1.2-appindicator3-0.1 \
    wireplumber smartmontools

# Clone and install
git clone https://github.com/sagardn/universal-system-monitor.git
cd universal-system-monitor
bash install.sh
```

**Or install the .deb package:**

```bash
# Build .deb
bash build-deb.sh

# Install
sudo dpkg -i dist/universal-system-monitor_0.2.0_amd64.deb
sudo apt install -f
systemctl --user enable --now usm
```

### Fedora

```bash
# Install dependencies
sudo dnf install python3 python3-psutil python3-aiohttp python3-pillow \
    webkit2gtk4.1 libappindicator-gtk3 wireplumber smartmontools

# Clone and install
git clone https://github.com/sagardn/universal-system-monitor.git
cd universal-system-monitor
bash install.sh
```

---

## 🎯 Usage

### Commands

```bash
usm                    # Start USM daemon (foreground)
systemctl --user start usm    # Start as background service
systemctl --user stop usm     # Stop service
systemctl --user restart usm  # Restart service
systemctl --user status usm   # Check status
```

### Dashboard

Open **http://127.0.0.1:7777** in any browser, or click the system tray icon.

### System Tray

The USM icon appears in your system tray (next to network/sound/brightness):

- **Left click** → Opens native dashboard window
- **Right click** → Menu: Open Dashboard, Restart, Quit

> **Note:** If the tray icon is hidden, right-click the system tray → **Configure System Tray** → set "usm-monitor" to **Always Visible**.

---

## 🏠 Architecture

```
universal-system-monitor/
├── daemon/                  # Python backend
│   ├── main.py             # Entry point, starts all collectors
│   ├── server.py           # aiohttp web server + WebSocket
│   ├── config.py           # Configuration management
│   ├── collectors/         # Data collectors (20+ modules)
│   │   ├── system.py       # CPU, RAM, swap
│   │   ├── gpu.py          # NVIDIA/AMD GPU
│   │   ├── battery.py      # Battery + power profiles
│   │   ├── network.py      # Network interfaces + WiFi
│   │   ├── docker.py       # Docker containers
│   │   ├── pipewire.py     # Audio (PipeWire/WirePlumber)
│   │   ├── thermal.py      # Temperature sensors
│   │   ├── disks.py        # SMART health
│   │   └── ...
│   ├── actions/            # User-triggered actions via WebSocket
│   │   ├── process_actions.py
│   │   ├── docker_actions.py
│   │   ├── service_actions.py
│   │   ├── pipewire_actions.py
│   │   ├── cleanup_actions.py
│   │   └── ...
│   ├── alerts/             # Alert engine + watchdog
│   ├── storage/            # SQLite metrics database
│   ├── tray.py             # Tray icon launcher
│   ├── tray_app.py         # Standalone tray process
│   └── viewer.py           # Native GTK+WebKit window
├── frontend/               # React (Vite) dashboard
│   ├── src/
│   │   ├── pages/          # 19 dashboard pages
│   │   ├── components/     # Shared UI components
│   │   └── hooks/          # WebSocket hooks
│   └── dist/               # Built frontend (served by daemon)
├── assets/
│   └── usm-icon.png        # App icon
├── install.sh              # Linux installer
├── uninstall.sh            # Uninstaller
├── build-deb.sh            # .deb package builder
├── PKGBUILD                # Arch Linux package
└── pyproject.toml          # Python project config
```

### How it works

1. **Daemon** starts collectors that gather system data every 1-60 seconds
2. **WebSocket** streams real-time data to all connected clients
3. **Frontend** renders the data in a premium React dashboard
4. **Actions** let you control the system (kill processes, manage Docker, adjust volume, etc.)
5. **Tray icon** provides quick access from the system tray

---

## 🗑️ Uninstall

```bash
bash uninstall.sh
```

Or manually:

```bash
systemctl --user stop usm
systemctl --user disable usm
rm -rf ~/.local/share/usm
rm -f ~/.local/bin/usm ~/.local/bin/usm-desktop
rm -f ~/.config/systemd/user/usm.service
rm -f ~/.local/share/applications/usm.desktop
rm -f ~/.local/share/icons/hicolor/256x256/apps/usm.png
systemctl --user daemon-reload
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for Linux users
</p>
