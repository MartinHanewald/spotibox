#!/usr/bin/env bash
# setup_poweroff.sh — Configure GPIO16 to signal the Pololu mini power switch
#                     to cut power after the Raspberry Pi has fully shut down.
#
# Wiring:
#   GPIO16 (Pin 36) → Pololu mini power switch CTRL / OFF pin
#
# The gpio-poweroff Device Tree overlay drives GPIO16 high for 100ms after
# the kernel halts, triggering the Pololu switch to cut VIN completely.
# No software timers or Python code required.
#
# Usage:
#   sudo bash scripts/setup_poweroff.sh
#   # then reboot

set -euo pipefail

CONFIG="/boot/firmware/config.txt"
OVERLAY_LINE="dtoverlay=gpio-poweroff,gpiopin=16"
COMMENT_LINE="# Pololu mini power switch: drive GPIO16 high on shutdown to cut power"

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "=== Pololu Power Switch (GPIO16) Setup ==="

# Remove any existing gpio-poweroff line to avoid duplicates
if grep -q "^dtoverlay=gpio-poweroff" "$CONFIG"; then
    sed -i '/^# Pololu mini power switch.*$/d' "$CONFIG"
    sed -i '/^dtoverlay=gpio-poweroff/d' "$CONFIG"
    echo "[OK] Removed old gpio-poweroff entry"
fi

# Append to config
cat >> "$CONFIG" << EOF

${COMMENT_LINE}
${OVERLAY_LINE}
EOF

echo "[OK] Added: ${OVERLAY_LINE}"
echo ""
echo "Current gpio-poweroff config in ${CONFIG}:"
echo "------"
grep -E "gpio-poweroff|Pololu" "$CONFIG"
echo "------"
echo ""
echo "Reboot required to apply changes:"
echo "  sudo reboot"
