# Maintainer: USM Team
pkgname=universal-system-monitor
pkgver=0.2.0
pkgrel=1
pkgdesc="Real-time system monitor — CPU, GPU, Network, Audio, Docker & more"
arch=('x86_64')
url="https://github.com/sagardn/universal-system-monitor"
license=('MIT')
depends=(
    'python>=3.10'
    'python-psutil'
    'python-aiohttp'
    'python-pillow'
    'python-aiosqlite'
)
optdepends=(
    'smartmontools: Disk SMART health monitoring'
    'wireplumber: Audio volume control'
    'docker: Container monitoring'
    'python-pystray: System tray icon'
)
makedepends=('python-build' 'python-installer' 'python-hatchling')
source=()
noextract=()

# Build from local source
build() {
    cd "$startdir"
    # Frontend is pre-built in frontend/dist/
    if [ ! -d "frontend/dist" ]; then
        echo "Error: frontend/dist not found. Run 'bun run build' in frontend/ first."
        return 1
    fi
}

package() {
    cd "$startdir"

    # Install app to /opt/usm
    install -dm755 "$pkgdir/opt/usm"
    cp -r daemon "$pkgdir/opt/usm/"
    cp -r frontend/dist "$pkgdir/opt/usm/frontend-dist"
    mkdir -p "$pkgdir/opt/usm/frontend"
    cp -r frontend/dist "$pkgdir/opt/usm/frontend/dist"
    cp pyproject.toml "$pkgdir/opt/usm/"

    # Assets
    if [ -d "assets" ]; then
        cp -r assets "$pkgdir/opt/usm/"
    fi

    # Clean pycache
    find "$pkgdir/opt/usm" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$pkgdir/opt/usm" -name "*.pyc" -delete 2>/dev/null || true

    # Launcher script
    install -Dm755 /dev/stdin "$pkgdir/usr/bin/usm" << 'EOF'
#!/usr/bin/env bash
USM_DIR="/opt/usm"
if [ ! -d "$USM_DIR/.venv" ]; then
    echo "First run: setting up Python environment..."
    cd "$USM_DIR"
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install -e "." --quiet 2>/dev/null || true
fi
cd "$USM_DIR"
exec "$USM_DIR/.venv/bin/python" -m daemon.main "$@"
EOF

    # Systemd user service
    install -Dm644 /dev/stdin "$pkgdir/usr/lib/systemd/user/usm.service" << 'EOF'
[Unit]
Description=Universal System Monitor
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/usm
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

    # Desktop entry
    install -Dm644 /dev/stdin "$pkgdir/usr/share/applications/usm.desktop" << 'EOF'
[Desktop Entry]
Name=Universal System Monitor
Comment=Real-time system monitor dashboard
Exec=xdg-open http://127.0.0.1:7777
Icon=usm
Terminal=false
Type=Application
Categories=System;Monitor;
Keywords=system;monitor;cpu;gpu;docker;network;
EOF

    # Icon
    if [ -f "assets/usm-icon.png" ]; then
        install -Dm644 "assets/usm-icon.png" \
            "$pkgdir/usr/share/icons/hicolor/256x256/apps/usm.png"
    fi
}
