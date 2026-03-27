#!/usr/bin/env bash
# setup_buttons.sh — Install system dependencies for GPIO button support (lgpio)
#
# The lgpio Python package requires native build tools and the lgpio C library
# to compile from source.  This script installs those system packages, then
# syncs the uv environment so the lgpio wheel is built and available.
#
# GPIO Pin Mapping (BCM numbering):
#   GPIO  4 → PLAY1  (album1)
#   GPIO 27 → PLAY2  (album2)
#   GPIO 22 → PLAY3  (album3)
#   GPIO  5 → PLAY4  (album4) / PLAY7 (album7) via MultiButtonBoard
#   GPIO  6 → PLAY5  (album5) / PLAY7 (album7) via MultiButtonBoard
#   GPIO 13 → PLAY6  (album6) / PLAY8 (album8) via MultiButtonBoard
#   GPIO 26 → PAUSE/RESUME   / PLAY8 (album8) via MultiButtonBoard
#   GPIO 14 → VOL UP
#   GPIO 15 → VOL DOWN
#   GPIO 12 → NEXT
#   GPIO 23 → LED indicator
#
# Usage:
#   sudo bash scripts/setup_buttons.sh
#
# After setup, verify with:
#   uv run python scripts/test_buttons.py
#   uv run python scripts/monitor_buttons.py

set -euo pipefail

# --- Build dependencies needed to compile the lgpio Python package ---
SYSTEM_DEPS=(swig python3-dev liblgpio-dev)

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "=== Spotibox Button / GPIO Setup ==="
echo ""

# -----------------------------------------------------------
# 1. Install system build dependencies
# -----------------------------------------------------------
echo "--- Step 1: System packages ---"

MISSING=()
for pkg in "${SYSTEM_DEPS[@]}"; do
    if dpkg -s "$pkg" &>/dev/null; then
        echo "[OK] $pkg already installed"
    else
        MISSING+=("$pkg")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Installing: ${MISSING[*]} ..."
    apt-get update -qq
    apt-get install -y "${MISSING[@]}"
    echo "[OK] System packages installed"
else
    echo "[OK] All system packages already present"
fi
echo ""

# -----------------------------------------------------------
# 2. Sync uv environment (builds lgpio wheel)
# -----------------------------------------------------------
echo "--- Step 2: Python environment (uv sync) ---"

# Run uv sync as the owning user, not as root
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OWNER="$(stat -c '%U' "$PROJ_DIR")"

if [[ "$OWNER" == "root" ]]; then
    cd "$PROJ_DIR" && uv sync --group dev
else
    su - "$OWNER" -c "cd '$PROJ_DIR' && uv sync --group dev"
fi
echo "[OK] uv environment synced"
echo ""

# -----------------------------------------------------------
# 3. Verify lgpio imports
# -----------------------------------------------------------
echo "--- Step 3: Verify lgpio ---"

if su - "$OWNER" -c "cd '$PROJ_DIR' && uv run python -c 'import lgpio; print(f\"lgpio {lgpio.get_lgpio_version()}\")'" 2>/dev/null; then
    echo "[OK] lgpio available"
else
    echo "[FAIL] lgpio import failed" >&2
    exit 1
fi

if su - "$OWNER" -c "cd '$PROJ_DIR' && uv run python -c 'from gpiozero import Button; print(\"gpiozero OK\")'" 2>/dev/null; then
    echo "[OK] gpiozero with lgpio pin factory available"
else
    echo "[FAIL] gpiozero import failed" >&2
    exit 1
fi
echo ""

echo "=== Setup complete ==="
echo ""
echo "Test buttons interactively:"
echo "  uv run python scripts/test_buttons.py"
echo ""
echo "Monitor all buttons in real time:"
echo "  uv run python scripts/monitor_buttons.py"
