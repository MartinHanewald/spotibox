#!/usr/bin/env bash
# setup_services.sh — Install and enable spotibox systemd services
#
# Installs two services:
#   1. spotibox.service         — main player (after audio + display ready)
#   2. spotibox-shutdown.service — GPIO 26 shutdown button monitor
#
# Usage:
#   sudo bash scripts/setup_services.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="/etc/systemd/system"

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "=== Spotibox Service Setup ==="
echo ""

# --- 0. Ensure log directory exists and is owned by admin ---
mkdir -p /var/log/spotibox
chown admin:admin /var/log/spotibox
chmod 755 /var/log/spotibox
echo "[OK] Log directory /var/log/spotibox ready"

# Add admin to systemd-journal group so analyze_startup.py can read journald
if ! groups admin | grep -q systemd-journal; then
    usermod -aG systemd-journal admin
    echo "[OK] Added admin to systemd-journal group (re-login required for effect)"
else
    echo "[OK] admin already in systemd-journal group"
fi

# --- 1. Install service files ---
for svc in spotibox.service spotibox-shutdown.service spotibox-monitor.service; do
    src="$SCRIPT_DIR/$svc"
    dst="$SERVICE_DIR/$svc"
    if [[ ! -f "$src" ]]; then
        echo "[ERROR] $src not found" >&2
        exit 1
    fi
    cp "$src" "$dst"
    echo "[OK] Installed $dst"
done

# --- 2. Ensure the admin user can run shutdown without a password ---
SUDOERS_FILE="/etc/sudoers.d/spotibox-shutdown"
if [[ ! -f "$SUDOERS_FILE" ]]; then
    echo "admin ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/reboot" > "$SUDOERS_FILE"
    chmod 0440 "$SUDOERS_FILE"
    echo "[OK] Passwordless sudo for shutdown/reboot configured"
else
    # Update if reboot is missing
    if ! grep -q reboot "$SUDOERS_FILE"; then
        echo "admin ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/reboot" > "$SUDOERS_FILE"
        chmod 0440 "$SUDOERS_FILE"
        echo "[OK] Passwordless sudo updated (added reboot)"
    else
        echo "[OK] Sudoers rule already exists"
    fi
fi

# --- 3. Reload and enable ---
systemctl daemon-reload
echo "[OK] systemd reloaded"

systemctl enable spotibox.service
echo "[OK] spotibox.service enabled"

systemctl enable spotibox-shutdown.service
echo "[OK] spotibox-shutdown.service enabled"

systemctl enable spotibox-monitor.service
echo "[OK] spotibox-monitor.service enabled"

echo ""
echo "=== Services Installed ==="
echo ""
echo "  spotibox.service          — main player"
echo "    Starts after: network, sound, raspotify, ILI9341 framebuffer"
echo "    Reads credentials from: /home/admin/spotibox/.env"
echo ""
echo "  spotibox-shutdown.service — shutdown button (GPIO 26, hold 3s)"
echo ""
echo "  spotibox-monitor.service  — power/load metrics collector"
echo "    Writes JSONL logs to:   /var/log/spotibox/power_*.jsonl"
echo "    Starts before spotibox.service to capture full startup"
echo ""
echo "Commands:"
echo "  sudo systemctl start spotibox          # start now"
echo "  sudo systemctl stop spotibox           # stop"
echo "  sudo systemctl status spotibox         # check status"
echo "  journalctl -u spotibox -f              # follow logs"
echo "  journalctl -u spotibox-monitor -f      # follow power monitor"
echo ""
echo "Analyse startup after booting:"
echo "  uv run python scripts/analyze_startup.py"
echo "  # then open startup_report.html in a browser"
echo ""
echo "All services will start automatically on next boot."
