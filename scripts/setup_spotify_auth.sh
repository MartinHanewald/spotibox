#!/usr/bin/env bash
# setup_spotify_auth.sh — Authenticate Raspotify (librespot) with a Spotify account
#
# Runs librespot's headless OAuth flow to cache credentials so that
# the SPOTIBOX device appears for the account without needing another
# device to stream to it first.
#
# Password authentication is no longer supported by librespot.
# This script uses the headless OAuth flow: it prints a URL you open
# in a browser on any machine, complete the login, then paste the
# redirect URL back into this script.
#
# Prerequisites:
#   - Raspotify must be installed (run scripts/setup_audio.sh first)
#   - You need a Spotify Premium account
#
# Usage:
#   sudo bash scripts/setup_spotify_auth.sh
#
# After completion, restart raspotify:
#   sudo systemctl restart raspotify

set -euo pipefail

DEVICE_NAME="SPOTIBOX"
CACHE_DIR="/var/cache/raspotify"
RASPOTIFY_CONF="/etc/raspotify/conf"

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

if ! command -v librespot &>/dev/null; then
    echo "Error: librespot not found. Install Raspotify first:" >&2
    echo "  sudo bash scripts/setup_audio.sh" >&2
    exit 1
fi

echo "=== Spotibox Spotify Authentication ==="
echo ""
echo "This will run librespot's headless OAuth flow."
echo "You will need a web browser on any device (phone, laptop, etc.)."
echo ""

# Ensure cache directory exists
mkdir -p "$CACHE_DIR"
chown raspotify:raspotify "$CACHE_DIR" 2>/dev/null || true

# Stop raspotify so librespot can bind to the same ports
echo "Stopping raspotify service..."
systemctl stop raspotify 2>/dev/null || true
echo ""

# -----------------------------------------------------------
# Run headless OAuth flow
# -----------------------------------------------------------
echo "--- Starting OAuth authentication ---"
echo ""
echo "  1. A URL will appear below — open it in any web browser"
echo "  2. Log in with your Spotify Premium account"
echo "  3. After login, the browser will redirect to a URL starting"
echo "     with http://127.0.0.1/login?code=..."
echo "  4. Copy that ENTIRE redirect URL and paste it back here"
echo ""
echo "Starting librespot OAuth (press Ctrl+C to cancel)..."
echo ""

# --oauth-port 0 disables the local redirect server (headless mode)
# --system-cache stores credentials persistently
# --name ensures the device name matches
librespot \
    --name "$DEVICE_NAME" \
    --system-cache "$CACHE_DIR" \
    --enable-oauth \
    --oauth-port 0

OAUTH_EXIT=$?

echo ""

if [[ $OAUTH_EXIT -ne 0 ]]; then
    echo "[ERROR] OAuth flow failed (exit code: $OAUTH_EXIT)." >&2
    echo "  Restarting raspotify..."
    systemctl start raspotify 2>/dev/null || true
    exit 1
fi

# -----------------------------------------------------------
# Verify credentials were cached
# -----------------------------------------------------------
if [[ -f "$CACHE_DIR/credentials.json" ]]; then
    echo "[OK] Credentials cached successfully at $CACHE_DIR/credentials.json"

    # Extract username and configure it in raspotify conf
    if command -v python3 &>/dev/null; then
        SPOTIFY_USER=$(python3 -c "
import json, sys
try:
    with open('$CACHE_DIR/credentials.json') as f:
        print(json.load(f).get('username', ''))
except Exception:
    sys.exit(1)
" 2>/dev/null || true)

        if [[ -n "$SPOTIFY_USER" ]]; then
            echo "[OK] Authenticated as: $SPOTIFY_USER"

            # Set LIBRESPOT_USERNAME in raspotify conf
            if grep -q "^LIBRESPOT_USERNAME=" "$RASPOTIFY_CONF"; then
                sed -i "s|^LIBRESPOT_USERNAME=.*|LIBRESPOT_USERNAME=\"$SPOTIFY_USER\"|" "$RASPOTIFY_CONF"
            else
                sed -i "s|^#\\?LIBRESPOT_USERNAME=.*|LIBRESPOT_USERNAME=\"$SPOTIFY_USER\"|" "$RASPOTIFY_CONF"
            fi
            echo "[OK] LIBRESPOT_USERNAME set to '$SPOTIFY_USER' in $RASPOTIFY_CONF"
        fi
    fi

    # Ensure file permissions are correct
    chown raspotify:raspotify "$CACHE_DIR/credentials.json" 2>/dev/null || true
    chmod 600 "$CACHE_DIR/credentials.json"
    echo "[OK] Credential file permissions secured"
else
    echo "[WARN] No credentials.json found in $CACHE_DIR"
    echo "  The OAuth flow may not have completed successfully."
    echo "  Try running this script again."
fi

# -----------------------------------------------------------
# Restart raspotify
# -----------------------------------------------------------
echo ""
echo "Restarting raspotify..."
systemctl start raspotify
sleep 2

if systemctl is-active --quiet raspotify; then
    echo "[OK] Raspotify is running"
else
    echo "[WARN] Raspotify may not be running — check: journalctl -u raspotify"
fi

echo ""
echo "=== Authentication Complete ==="
echo ""
echo "  '$DEVICE_NAME' should now appear as a Spotify Connect device"
echo "  for your account without needing another device to connect first."
echo ""
echo "  To re-authenticate (e.g. different account), run this script again."
