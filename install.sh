#!/usr/bin/env bash
# ============================================================
#  Universal System Monitor — Linux Install Script
#  Installs USM as a systemd user service with desktop entry
# ============================================================
set -euo pipefail

APP_NAME="universal-system-monitor"
APP_DIR="$HOME/.local/share/usm"
BIN_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🖥️  Universal System Monitor"
echo "  Installing to $APP_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Stop existing service if running
echo "→ Stopping existing service (if any)..."
systemctl --user stop usm.service 2>/dev/null || true

# 2. Create directories
echo "→ Creating directories..."
mkdir -p "$APP_DIR" "$BIN_DIR" "$SERVICE_DIR" "$DESKTOP_DIR" "$ICON_DIR"

# 3. Copy project files
echo "→ Copying project files..."
rsync -a --delete \
    --exclude '.git' \
    --exclude '.github' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    --exclude '*.pyc' \
    --exclude 'frontend/node_modules' \
    --exclude 'frontend/src' \
    --exclude 'frontend/public' \
    --exclude 'frontend/vite.config.js' \
    --exclude 'frontend/package.json' \
    --exclude 'frontend/bun.lockb' \
    "$SCRIPT_DIR/" "$APP_DIR/"

# 4. Set up Python venv with uv
echo "→ Setting up Python environment..."
cd "$APP_DIR"
# Must use system Python (not uv's) to access system gi/GTK packages
/usr/bin/python3 -m venv --clear --system-site-packages .venv
if command -v uv &>/dev/null; then
    uv pip install -e "." --quiet
else
    .venv/bin/pip install -e "." --quiet
fi

# 5. Create launcher scripts
echo "→ Creating launchers..."

# CLI/service launcher
cat > "$BIN_DIR/usm" << 'LAUNCHER'
#!/usr/bin/env bash
USM_DIR="$HOME/.local/share/usm"
exec "$USM_DIR/.venv/bin/python" -m daemon.main "$@"
LAUNCHER
chmod +x "$BIN_DIR/usm"

# Desktop app launcher
cat > "$BIN_DIR/usm-desktop" << 'LAUNCHER'
#!/usr/bin/env bash
USM_DIR="$HOME/.local/share/usm"
cd "$USM_DIR"
exec "$USM_DIR/.venv/bin/python" -m daemon.desktop "$@"
LAUNCHER
chmod +x "$BIN_DIR/usm-desktop"

# 6. Create systemd user service
echo "→ Creating systemd service..."
cat > "$SERVICE_DIR/usm.service" << 'SVCEOF'
[Unit]
Description=Universal System Monitor
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/usm
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SVCEOF

# 7. Create desktop entry
echo "→ Creating desktop entry..."
cat > "$DESKTOP_DIR/usm.desktop" << EOF
[Desktop Entry]
Name=Universal System Monitor
Comment=Monitor your system — CPU, GPU, Network, Audio, Docker & more
Exec=$BIN_DIR/usm-desktop
Icon=usm
Terminal=false
Type=Application
Categories=System;Monitor;
Keywords=system;monitor;cpu;gpu;docker;network;
StartupNotify=true
StartupWMClass=pywebview
EOF

# 8. Install app icon
echo "→ Installing icon..."
if [ -f "$APP_DIR/assets/usm-icon.png" ]; then
    cp "$APP_DIR/assets/usm-icon.png" "$ICON_DIR/usm.png"
    echo "  ✓ Icon installed"
else
    echo "  ⚠️  Icon file not found, skipping"
fi

# 9. Reload systemd and enable service
echo "→ Enabling service..."
systemctl --user daemon-reload
systemctl --user enable usm.service
systemctl --user start usm.service

# 10. Update desktop database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ USM installed successfully!"
echo ""
echo "  🌐 Dashboard: http://127.0.0.1:7777"
echo "  🔧 Command:   usm"
echo "  📋 Service:   systemctl --user status usm"
echo "  🔄 Restart:   systemctl --user restart usm"
echo "  ❌ Stop:      systemctl --user stop usm"
echo "  🗑️  Uninstall: $SCRIPT_DIR/uninstall.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
