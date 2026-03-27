#!/usr/bin/env bash
# setup_audio.sh — Install and configure WM8960 Audio HAT + Raspotify (Spotify Connect)
#
# WM8960 I2S/I2C wiring (BCM numbering):
#   GPIO2  → I2C SDA  (WM8960 control)
#   GPIO3  → I2C SCL  (WM8960 control)
#   GPIO18 → I2S BCLK (bit clock)
#   GPIO19 → I2S LRCLK (frame sync)
#   GPIO20 → I2S DIN  (PCM data in / capture)
#   GPIO21 → I2S DOUT (PCM data out / playback)
#
# This script:
#   1. Installs the Waveshare WM8960 sound card driver (DKMS kernel module)
#   2. Installs Raspotify (librespot — Spotify Connect client)
#   3. Configures Raspotify to advertise as "SPOTIBOX" on the WM8960 audio device
#
# The spotibox app expects a Spotify Connect device named "SPOTIBOX" (see
# DEVICE_NAME in spotibox/spotibox.py).
#
# Usage:
#   sudo bash scripts/setup_audio.sh
#   # then reboot
#
# After reboot, verify with:
#   bash scripts/test_audio.sh

set -euo pipefail

DEVICE_NAME="SPOTIBOX"
ALSA_DEVICE="plughw:CARD=wm8960soundcard,DEV=0"
RASPOTIFY_CONF="/etc/raspotify/conf"
WM8960_REPO="https://github.com/waveshare/WM8960-Audio-HAT"
WM8960_TMPDIR="/tmp/WM8960-Audio-HAT"

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "=== Spotibox Audio Setup ==="
echo ""

# -----------------------------------------------------------
# 1. Install WM8960 Sound Card Driver
# -----------------------------------------------------------
echo "--- Step 1: WM8960 Sound Card Driver ---"

if aplay -l 2>/dev/null | grep -q "wm8960soundcard"; then
    echo "[OK] WM8960 sound card already detected — skipping driver install"
else
    echo "Installing WM8960 driver from $WM8960_REPO ..."
    rm -rf "$WM8960_TMPDIR"
    apt-get update -qq
    apt-get -y install git
    git clone "$WM8960_REPO" "$WM8960_TMPDIR"
    cd "$WM8960_TMPDIR"
    ./install.sh
    cd /
    rm -rf "$WM8960_TMPDIR"
    echo "[OK] WM8960 driver installed (reboot required)"
fi
echo ""

# -----------------------------------------------------------
# 2. Install Raspotify
# -----------------------------------------------------------
echo "--- Step 2: Raspotify (Spotify Connect) ---"

if dpkg -l raspotify &>/dev/null; then
    echo "[OK] Raspotify already installed: $(dpkg -l raspotify | awk '/raspotify/{print $3}')"
else
    echo "Installing Raspotify..."
    apt-get -y install curl
    curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
    echo "[OK] Raspotify installed"
fi
echo ""

# -----------------------------------------------------------
# 3. Configure Raspotify
# -----------------------------------------------------------
echo "--- Step 3: Configure Raspotify as '$DEVICE_NAME' ---"

if [[ ! -f "$RASPOTIFY_CONF" ]]; then
    echo "[ERROR] Raspotify config not found at $RASPOTIFY_CONF" >&2
    exit 1
fi

# Device name → SPOTIBOX (matches DEVICE_NAME in spotibox/spotibox.py)
if grep -q "^LIBRESPOT_NAME=\"$DEVICE_NAME\"" "$RASPOTIFY_CONF"; then
    echo "[OK] Device name already set to '$DEVICE_NAME'"
else
    sed -i "s|^#\\?LIBRESPOT_NAME=.*|LIBRESPOT_NAME=\"$DEVICE_NAME\"|" "$RASPOTIFY_CONF"
    echo "[OK] Device name set to '$DEVICE_NAME'"
fi

# Audio device → WM8960 sound card
if grep -q "^LIBRESPOT_DEVICE=\"$ALSA_DEVICE\"" "$RASPOTIFY_CONF"; then
    echo "[OK] Audio device already set to '$ALSA_DEVICE'"
else
    sed -i "s|^#\\?LIBRESPOT_DEVICE=.*|LIBRESPOT_DEVICE=\"$ALSA_DEVICE\"|" "$RASPOTIFY_CONF"
    echo "[OK] Audio device set to '$ALSA_DEVICE'"
fi

# Bitrate → 320 kbps (max quality)
sed -i 's|^#\?LIBRESPOT_BITRATE=.*|LIBRESPOT_BITRATE="320"|' "$RASPOTIFY_CONF"
echo "[OK] Bitrate set to 320 kbps"

# Device type → speaker
sed -i 's|^#\?LIBRESPOT_DEVICE_TYPE=.*|LIBRESPOT_DEVICE_TYPE=speaker|' "$RASPOTIFY_CONF"
echo "[OK] Device type set to speaker"

# Initial volume → 50%
sed -i 's|^#\?LIBRESPOT_INITIAL_VOLUME=.*|LIBRESPOT_INITIAL_VOLUME=50|' "$RASPOTIFY_CONF"
echo "[OK] Initial volume set to 50%"

# System cache → persistent directory for credential storage
CACHE_DIR="/var/cache/raspotify"
mkdir -p "$CACHE_DIR"
chown raspotify:raspotify "$CACHE_DIR" 2>/dev/null || true
if grep -q "^LIBRESPOT_SYSTEM_CACHE=\"$CACHE_DIR\"" "$RASPOTIFY_CONF"; then
    echo "[OK] System cache already set to '$CACHE_DIR'"
else
    sed -i "s|^#\\?LIBRESPOT_SYSTEM_CACHE=.*|LIBRESPOT_SYSTEM_CACHE=\"$CACHE_DIR\"|" "$RASPOTIFY_CONF"
    echo "[OK] System cache set to '$CACHE_DIR'"
fi

# Ensure credential caching is enabled (comment out the disable flag)
if grep -q "^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=" "$RASPOTIFY_CONF"; then
    sed -i 's|^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=|#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=|' "$RASPOTIFY_CONF"
    echo "[OK] Credential caching enabled (was disabled)"
else
    echo "[OK] Credential caching is enabled"
fi

echo ""

# -----------------------------------------------------------
# 4. Enable and restart Raspotify
# -----------------------------------------------------------
echo "--- Step 4: Enable Raspotify service ---"

systemctl enable raspotify
systemctl restart raspotify
sleep 2

if systemctl is-active --quiet raspotify; then
    echo "[OK] Raspotify service is active"
else
    echo "[WARN] Raspotify service may not be running — check: journalctl -u raspotify"
fi
echo ""

# -----------------------------------------------------------
# 5. Set ALSA volume to maximum (full software control via Spotify)
# -----------------------------------------------------------
echo "--- Step 5: Set ALSA volume to 100% ---"

if amixer -c wm8960soundcard sset Speaker 100% &>/dev/null; then
    echo "[OK] Speaker volume set to 100%"
else
    echo "[WARN] Could not set Speaker volume — sound card may not be ready yet"
fi

if amixer -c wm8960soundcard sset Playback 100% &>/dev/null; then
    echo "[OK] Playback volume set to 100%"
else
    echo "[WARN] Could not set Playback volume"
fi

# Persist ALSA state so it survives reboot
if command -v alsactl &>/dev/null; then
    alsactl store &>/dev/null || true
    echo "[OK] ALSA state saved"
fi

if systemctl is-active --quiet raspotify; then
    echo "[OK] Raspotify service is active"
else
    echo "[WARN] Raspotify service may not be running — check: journalctl -u raspotify"
fi
echo ""

# -----------------------------------------------------------
# Summary
# -----------------------------------------------------------
echo "=== Audio Setup Complete ==="
echo ""
echo "Configuration:"
echo "  Device name:   $DEVICE_NAME"
echo "  ALSA device:   $ALSA_DEVICE"
echo "  Bitrate:       320 kbps"
echo "  System cache:  $CACHE_DIR"
echo "  Config file:   $RASPOTIFY_CONF"
echo ""

if ! aplay -l 2>/dev/null | grep -q "wm8960soundcard"; then
    echo "*** REBOOT REQUIRED for WM8960 driver to take effect ***"
    echo "  sudo reboot"
else
    echo "WM8960 sound card is active. Raspotify should be discoverable"
    echo "as '$DEVICE_NAME' on your local network."
    echo ""
    echo "Verify with:"
    echo "  bash scripts/test_audio.sh"
fi

echo ""
echo "=== Next Step: Authenticate with Spotify ==="
echo ""
echo "  Run the OAuth setup to link your Spotify account:"
echo "    sudo bash scripts/setup_spotify_auth.sh"
echo ""
echo "  This is required so that '$DEVICE_NAME' appears as a"
echo "  device for your account without needing another device"
echo "  to stream to it first."
