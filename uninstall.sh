#!/usr/bin/env bash
# ============================================================
#  Universal System Monitor — Uninstall Script
# ============================================================
set -euo pipefail

echo "🗑️  Uninstalling Universal System Monitor..."

# Stop and disable service
systemctl --user stop usm.service 2>/dev/null || true
systemctl --user disable usm.service 2>/dev/null || true

# Remove files
rm -f "$HOME/.config/systemd/user/usm.service"
rm -f "$HOME/.local/bin/usm"
rm -f "$HOME/.local/share/applications/usm.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/usm.png"
rm -rf "$HOME/.local/share/usm"

# Reload
systemctl --user daemon-reload 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "✅ USM uninstalled."
echo "Note: User data at ~/.local/share/usm/metrics.db was removed."
echo "      To keep data, back it up before uninstalling."
