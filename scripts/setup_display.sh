#!/usr/bin/env bash
# setup_display.sh — Configure the ILI9341 2.2" SPI TFT display on Raspberry Pi
#
# Wiring (BCM numbering):
#   RESET  → GPIO24 (Pin 18)
#   DC     → GPIO25 (Pin 22)
#   LED    → GPIO23 (Pin 16)
#   CS     → GPIO8 / SPI0 CE0 (Pin 24)
#   MOSI   → GPIO10 (Pin 19)
#   MISO   → GPIO9 (Pin 21)
#   SCLK   → GPIO11 (Pin 23)
#   VCC    → 3.3V (Pin 1 or 17)
#   GND    → any GND pin
#
# Usage:
#   sudo bash scripts/setup_display.sh
#   # then reboot

set -euo pipefail

CONFIG="/boot/firmware/config.txt"
OVERLAY_LINE="dtoverlay=fbtft,spi0-0,ili9341,reset_pin=24,dc_pin=25,led_pin=23,rotate=90,speed=80000000,fps=60,bgr"

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "=== ILI9341 SPI Display Setup ==="

# 1. Enable SPI
if grep -q "^#dtparam=spi=on" "$CONFIG"; then
    sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "$CONFIG"
    echo "[OK] SPI enabled"
elif grep -q "^dtparam=spi=on" "$CONFIG"; then
    echo "[OK] SPI already enabled"
else
    echo "dtparam=spi=on" >> "$CONFIG"
    echo "[OK] SPI added"
fi

# 2. Add fbtft overlay (remove any existing entry first to avoid duplicates)
if grep -q "^dtoverlay=fbtft,.*ili9341" "$CONFIG"; then
    sed -i '/^dtoverlay=fbtft,.*ili9341/d' "$CONFIG"
    echo "[OK] Removed old fbtft overlay line"
fi
# Also remove the comment line if present
sed -i '/^# ILI9341 2.2" SPI TFT Display$/d' "$CONFIG"

cat >> "$CONFIG" << EOF

# ILI9341 2.2" SPI TFT Display
${OVERLAY_LINE}
EOF
echo "[OK] Added fbtft overlay: ${OVERLAY_LINE}"

# 3. Disable unused hardware to reduce power draw (helps prevent undervoltage)

# Bluetooth — not used by Spotibox
if grep -q "^dtoverlay=disable-bt" "$CONFIG"; then
    echo "[OK] Bluetooth already disabled"
else
    echo "" >> "$CONFIG"
    echo "# Disable unused hardware (reduce power draw / undervoltage)" >> "$CONFIG"
    echo "dtoverlay=disable-bt" >> "$CONFIG"
    echo "[OK] Bluetooth disabled"
fi

# HDMI — uses ~25 mA; not needed with the SPI display
if grep -q "^dtoverlay=vc4-kms-v3d" "$CONFIG"; then
    sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' "$CONFIG"
    echo "[OK] vc4-kms-v3d (HDMI) disabled"
elif grep -q "^#dtoverlay=vc4-kms-v3d" "$CONFIG"; then
    echo "[OK] vc4-kms-v3d (HDMI) already disabled"
fi

# Camera auto-detect — not used
if grep -q "^camera_auto_detect=1" "$CONFIG"; then
    sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' "$CONFIG"
    echo "[OK] Camera auto-detect disabled"
else
    echo "[OK] Camera auto-detect already off"
fi

# DSI display auto-detect — not used (we use SPI)
if grep -q "^display_auto_detect=1" "$CONFIG"; then
    sed -i 's/^display_auto_detect=1/display_auto_detect=0/' "$CONFIG"
    echo "[OK] DSI display auto-detect disabled"
else
    echo "[OK] DSI display auto-detect already off"
fi

# 4. Disable Bluetooth service
if systemctl is-enabled bluetooth &>/dev/null; then
    systemctl disable bluetooth
    echo "[OK] Bluetooth service disabled"
else
    echo "[OK] Bluetooth service already disabled"
fi

echo ""
echo "Current display config in ${CONFIG}:"
echo "------"
grep -E "ILI9341|disable-bt|act_led|camera_auto|display_auto|vc4-kms" "$CONFIG" | head -20
echo "------"
echo ""
echo "Reboot required to apply changes:"
echo "  sudo reboot"
