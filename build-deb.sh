#!/usr/bin/env bash
# ============================================================
#  Universal System Monitor — .deb Package Builder
#  Builds a self-contained .deb without dpkg-deb
#  Works on any Linux distro (uses ar + tar)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="0.2.0"
ARCH="amd64"
PKG_NAME="universal-system-monitor"
DEB_FILE="${SCRIPT_DIR}/dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"

BUILD_DIR="${SCRIPT_DIR}/dist/deb-build"
INSTALL_ROOT="${BUILD_DIR}/root"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📦 Building ${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "${SCRIPT_DIR}/dist"

# ─── 1. Build frontend ───────────────────────────────
echo "→ Building frontend..."
if [ -d "$SCRIPT_DIR/frontend/node_modules" ] || command -v bun &>/dev/null; then
    cd "$SCRIPT_DIR/frontend"
    bun run build 2>/dev/null || npm run build
    cd "$SCRIPT_DIR"
fi

# ─── 2. Create directory structure ────────────────────
echo "→ Creating package structure..."
mkdir -p "${INSTALL_ROOT}/opt/usm"
mkdir -p "${INSTALL_ROOT}/usr/bin"
mkdir -p "${INSTALL_ROOT}/usr/lib/systemd/user"
mkdir -p "${INSTALL_ROOT}/usr/share/applications"
mkdir -p "${INSTALL_ROOT}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${INSTALL_ROOT}/usr/share/doc/${PKG_NAME}"

# ─── 3. Copy application files ───────────────────────
echo "→ Copying application files..."
# Python daemon
cp -r "$SCRIPT_DIR/daemon" "${INSTALL_ROOT}/opt/usm/"
# Frontend dist
cp -r "$SCRIPT_DIR/frontend/dist" "${INSTALL_ROOT}/opt/usm/frontend-dist"
mkdir -p "${INSTALL_ROOT}/opt/usm/frontend"
cp -r "$SCRIPT_DIR/frontend/dist" "${INSTALL_ROOT}/opt/usm/frontend/dist"
# Project config
cp "$SCRIPT_DIR/pyproject.toml" "${INSTALL_ROOT}/opt/usm/"
# Assets
if [ -d "$SCRIPT_DIR/assets" ]; then
    cp -r "$SCRIPT_DIR/assets" "${INSTALL_ROOT}/opt/usm/"
fi

# Clean __pycache__
find "${INSTALL_ROOT}/opt/usm" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${INSTALL_ROOT}/opt/usm" -name "*.pyc" -delete 2>/dev/null || true

# ─── 4. Create launcher script ───────────────────────
echo "→ Creating launcher..."
cat > "${INSTALL_ROOT}/usr/bin/usm" << 'EOF'
#!/usr/bin/env bash
# Universal System Monitor launcher
USM_DIR="/opt/usm"

# Use system python with required packages
PYTHON=""
for p in python3 python; do
    if command -v "$p" &>/dev/null; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3 not found"
    exit 1
fi

# Setup venv on first run (if needed)
if [ ! -d "$USM_DIR/.venv" ]; then
    echo "First run: setting up Python environment..."
    cd "$USM_DIR"
    "$PYTHON" -m venv --system-site-packages .venv
    .venv/bin/pip install -e "." --quiet 2>/dev/null || true
fi

cd "$USM_DIR"
exec "$USM_DIR/.venv/bin/python" -m daemon.main "$@"
EOF
chmod 755 "${INSTALL_ROOT}/usr/bin/usm"

# ─── 5. Create systemd user service ──────────────────
echo "→ Creating systemd service..."
cat > "${INSTALL_ROOT}/usr/lib/systemd/user/usm.service" << 'EOF'
[Unit]
Description=Universal System Monitor
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/usm
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
EOF

# ─── 6. Create desktop entry ─────────────────────────
echo "→ Creating desktop entry..."
cat > "${INSTALL_ROOT}/usr/share/applications/usm.desktop" << 'EOF'
[Desktop Entry]
Name=Universal System Monitor
Comment=Real-time system monitor — CPU, GPU, Network, Audio, Docker & more
Exec=xdg-open http://127.0.0.1:7777
Icon=usm
Terminal=false
Type=Application
Categories=System;Monitor;
Keywords=system;monitor;cpu;gpu;docker;network;battery;
StartupNotify=false
EOF

# ─── 7. Install icon ─────────────────────────────────
echo "→ Installing icon..."
if [ -f "$SCRIPT_DIR/assets/usm-icon.png" ]; then
    cp "$SCRIPT_DIR/assets/usm-icon.png" \
       "${INSTALL_ROOT}/usr/share/icons/hicolor/256x256/apps/usm.png"
fi

# ─── 8. Create postinst script ───────────────────────
mkdir -p "${BUILD_DIR}/scripts"
cat > "${BUILD_DIR}/scripts/postinst" << 'POSTINST'
#!/bin/sh
set -e

# Create venv and install deps on first install
if [ ! -d /opt/usm/.venv ]; then
    echo "Setting up Python environment..."
    cd /opt/usm
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install -e "." --quiet 2>/dev/null || true
fi

# Update icon cache
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Universal System Monitor installed!"
echo ""
echo "  Start service:  systemctl --user enable --now usm"
echo "  Dashboard:      http://127.0.0.1:7777"
echo "  Command:        usm"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
POSTINST
chmod 755 "${BUILD_DIR}/scripts/postinst"

cat > "${BUILD_DIR}/scripts/prerm" << 'PRERM'
#!/bin/sh
# Stop service before removal
systemctl --user stop usm.service 2>/dev/null || true
systemctl --user disable usm.service 2>/dev/null || true
PRERM
chmod 755 "${BUILD_DIR}/scripts/prerm"

cat > "${BUILD_DIR}/scripts/postrm" << 'POSTRM'
#!/bin/sh
if [ "$1" = "purge" ] || [ "$1" = "remove" ]; then
    rm -rf /opt/usm/.venv 2>/dev/null || true
    rm -rf /opt/usm/__pycache__ 2>/dev/null || true
fi
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
POSTRM
chmod 755 "${BUILD_DIR}/scripts/postrm"

# ─── 9. Calculate installed size ─────────────────────
INSTALLED_SIZE=$(du -sk "${INSTALL_ROOT}" | cut -f1)

# ─── 10. Create DEBIAN/control ───────────────────────
echo "→ Creating control file..."
mkdir -p "${BUILD_DIR}/DEBIAN"
cat > "${BUILD_DIR}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Depends: python3 (>= 3.10), python3-venv, python3-pip
Recommends: python3-psutil, python3-aiohttp, python3-pil, smartmontools, wireplumber
Maintainer: USM Team <usm@localhost>
Homepage: https://github.com/sagardn/universal-system-monitor
Description: Universal System Monitor — Real-time system dashboard
 A modern, feature-rich system monitor with a web-based dashboard.
 Monitors CPU, GPU, RAM, disk, network, battery, Docker, audio,
 systemd services, security, and more. Built with Python + React.
EOF

# Copy scripts
cp "${BUILD_DIR}/scripts/postinst" "${BUILD_DIR}/DEBIAN/"
cp "${BUILD_DIR}/scripts/prerm" "${BUILD_DIR}/DEBIAN/"
cp "${BUILD_DIR}/scripts/postrm" "${BUILD_DIR}/DEBIAN/"

# ─── 11. Move root contents into DEBIAN parent ───────
# The .deb structure: data.tar.* (files) + control.tar.* (metadata) + debian-binary
echo "→ Building .deb package..."

# Create data tarball
cd "${INSTALL_ROOT}"
tar czf "${BUILD_DIR}/data.tar.gz" --owner=root --group=root .

# Create control tarball
cd "${BUILD_DIR}/DEBIAN"
tar czf "${BUILD_DIR}/control.tar.gz" --owner=root --group=root .

# Create debian-binary
echo "2.0" > "${BUILD_DIR}/debian-binary"

# Create .deb with ar
cd "${BUILD_DIR}"
ar rcs "$DEB_FILE" debian-binary control.tar.gz data.tar.gz

# ─── 12. Cleanup ─────────────────────────────────────
rm -rf "$BUILD_DIR"

# ─── Done ─────────────────────────────────────────────
DEB_SIZE=$(du -h "$DEB_FILE" | cut -f1)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Package built successfully!"
echo ""
echo "  📦 ${DEB_FILE}"
echo "  📏 Size: ${DEB_SIZE}"
echo ""
echo "  Install:   sudo dpkg -i ${DEB_FILE}"
echo "  Or:        sudo apt install ./${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
