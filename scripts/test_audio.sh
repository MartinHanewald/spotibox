#!/usr/bin/env bash
# test_audio.sh — Verify the WM8960 Audio HAT is working
#
# WM8960 I2S/I2C wiring (BCM numbering):
#   GPIO2  → I2C SDA  (WM8960 control)
#   GPIO3  → I2C SCL  (WM8960 control)
#   GPIO18 → I2S BCLK (bit clock)
#   GPIO19 → I2S LRCLK (frame sync)
#   GPIO20 → I2S DIN  (PCM data in / capture)
#   GPIO21 → I2S DOUT (PCM data out / playback)
#
# Usage:
#   bash scripts/test_audio.sh          # full test with audio playback
#   bash scripts/test_audio.sh --quick  # checks only, no audio playback

set -uo pipefail

CARD_NAME="wm8960soundcard"
PASS=0
FAIL=0
QUICK=false

[[ "${1:-}" == "--quick" ]] && QUICK=true

pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }

echo "=== WM8960 Audio HAT Integration Test ==="
echo ""

# 1. Check I2C bus is available
echo "1. I2C bus"
if ls /dev/i2c-* &>/dev/null; then
    pass "I2C device(s) found: $(ls /dev/i2c-*)"
else
    fail "No I2C devices found (/dev/i2c-*). Is I2C enabled in /boot/firmware/config.txt?"
fi

# 2. Check WM8960 on I2C bus (address 0x1a)
echo "2. WM8960 I2C presence (0x1a)"
if command -v i2cdetect &>/dev/null; then
    # Address 0x1a shows as "1a" (unbound) or "UU" (driver-bound) in row 10:
    I2C_ROW=$(i2cdetect -y 1 2>/dev/null | grep "^10:" || true)
    if echo "$I2C_ROW" | grep -qE "1a|UU"; then
        pass "WM8960 detected at I2C address 0x1a"
    else
        fail "WM8960 not found at I2C address 0x1a"
    fi
else
    fail "i2cdetect not installed (apt install i2c-tools)"
fi

# 3. Check kernel modules loaded
echo "3. Kernel modules"
if lsmod | grep -q "snd_soc_wm8960"; then
    pass "snd_soc_wm8960 module loaded"
else
    fail "snd_soc_wm8960 module not loaded"
fi

# 4. Check ALSA sound card
echo "4. ALSA sound card"
if aplay -l 2>/dev/null | grep -q "$CARD_NAME"; then
    CARD_LINE=$(aplay -l | grep "$CARD_NAME" | head -1)
    pass "Sound card found: $CARD_LINE"
else
    fail "Sound card '$CARD_NAME' not found in 'aplay -l'"
fi

# 5. Check wm8960-soundcard systemd service
echo "5. wm8960-soundcard service"
if systemctl is-active --quiet wm8960-soundcard 2>/dev/null; then
    pass "wm8960-soundcard.service is active"
elif systemctl list-unit-files | grep -q wm8960-soundcard; then
    fail "wm8960-soundcard.service exists but is not active"
else
    fail "wm8960-soundcard.service not found"
fi

# 6. Check device tree overlay
echo "6. Device tree overlay"
if grep -q "dtoverlay=wm8960-soundcard" /boot/firmware/config.txt 2>/dev/null; then
    pass "wm8960-soundcard overlay present in /boot/firmware/config.txt"
else
    fail "wm8960-soundcard overlay missing from /boot/firmware/config.txt"
fi

# 7. Check ALSA config
echo "7. ALSA configuration"
if [[ -f /etc/wm8960-soundcard/asound.conf ]] || [[ -f /etc/asound.conf ]]; then
    pass "ALSA config file found"
else
    fail "No ALSA config found (/etc/asound.conf or /etc/wm8960-soundcard/)"
fi

# 8. Audio playback test (unless --quick)
echo "8. Audio playback"
if $QUICK; then
    echo "  [SKIP] Skipped (--quick mode)"
elif ! aplay -l 2>/dev/null | grep -q "$CARD_NAME"; then
    fail "Cannot test playback — sound card not found"
else
    echo "  Playing test tone on $CARD_NAME for 3 seconds..."
    echo "  (You should hear 'Front Left' / 'Front Right' from the speaker)"
    if speaker-test -D hw:"$CARD_NAME" -c 2 -t wav -l 1 &>/dev/null; then
        pass "speaker-test completed without errors"
    else
        fail "speaker-test returned an error"
    fi
fi

# Summary
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -eq 0 ]]; then
    echo "All checks passed! WM8960 Audio HAT is working."
    exit 0
else
    echo "Some checks failed. See above for details."
    exit 1
fi
