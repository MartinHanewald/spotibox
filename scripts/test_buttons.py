#!/usr/bin/env python3
"""Interactive GPIO button integration test.

Prompts the user to press each physical button and verifies the GPIO
input is registered. Run this on the Raspberry Pi with buttons wired.

Usage:
    uv run python scripts/test_buttons.py
    uv run python scripts/test_buttons.py --timeout 10   # 10s per button
"""
from __future__ import annotations

import argparse
import sys
from time import sleep

from gpiozero import Button, LED

# Pin assignments (BCM numbering) — must match spotibox/spotibox.py _setup_buttons()
BUTTONS = {
    "PLAY1 (album1)":    4,
    "PLAY2 (album2)":   27,
    "PLAY3 (album3)":   22,
    "PLAY4 (album4)":    5,
    "PLAY5 (album5)":    6,
    "PLAY6 (album6)":   13,
    "PAUSE":            26,
    "VOL UP":           14,
    "VOL DOWN":         15,
    "NEXT":             12,
}

LED_PIN = 23


def test_led(led_pin: int) -> bool:
    """Blink the LED to confirm GPIO output works."""
    print(f"\n{'='*50}")
    print(f"LED Test (GPIO {led_pin})")
    print(f"{'='*50}")
    print("The LED should blink 3 times...")
    led = LED(led_pin)
    for _ in range(3):
        led.on()
        sleep(0.3)
        led.off()
        sleep(0.3)
    led.on()
    answer = input("Did you see the LED blink? [y/N] ").strip().lower()
    led.close()
    return answer == "y"


def test_button(name: str, pin: int, timeout: float) -> bool:
    """Wait for a single button press and report success/failure."""
    print(f"\n{'='*50}")
    print(f"Button: {name}  (GPIO {pin})")
    print(f"{'='*50}")
    print(f"Press the {name} button within {timeout:.0f} seconds...")

    btn = Button(pin, bounce_time=0.05)
    pressed = False

    def on_press():
        nonlocal pressed
        pressed = True

    btn.when_pressed = on_press

    elapsed = 0.0
    interval = 0.1
    while elapsed < timeout and not pressed:
        sleep(interval)
        elapsed += interval

    btn.close()

    if pressed:
        print(f"  [PASS] {name} pressed on GPIO {pin}")
    else:
        print(f"  [FAIL] {name} — no press detected on GPIO {pin} (timeout)")

    return pressed


def main():
    parser = argparse.ArgumentParser(description="Interactive GPIO button test")
    parser.add_argument(
        "--timeout", type=float, default=5.0,
        help="Seconds to wait for each button press (default: 5)",
    )
    parser.add_argument(
        "--skip-led", action="store_true",
        help="Skip the LED blink test",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  Spotibox GPIO Button Integration Test")
    print("=" * 50)
    print()
    print(f"Testing {len(BUTTONS)} buttons + LED")
    print(f"Timeout per button: {args.timeout:.0f}s")
    print()
    print("Pin mapping (BCM):")
    for name, pin in BUTTONS.items():
        print(f"  GPIO {pin:2d} → {name}")
    print(f"  GPIO {LED_PIN:2d} → LED")
    print()
    input("Press Enter to start...")

    passed = 0
    failed = 0
    results = []

    # LED test
    if not args.skip_led:
        ok = test_led(LED_PIN)
        results.append(("LED", LED_PIN, ok))
        if ok:
            passed += 1
        else:
            failed += 1

    # Button tests
    for name, pin in BUTTONS.items():
        ok = test_button(name, pin, args.timeout)
        results.append((name, pin, ok))
        if ok:
            passed += 1
        else:
            failed += 1

    # Summary
    total = passed + failed
    print()
    print("=" * 50)
    print(f"  Results: {passed}/{total} passed")
    print("=" * 50)
    for name, pin, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] GPIO {pin:2d} — {name}")
    print()

    if failed == 0:
        print("All buttons registered correctly!")
    else:
        print(f"{failed} button(s) failed. Check wiring and pin assignments.")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
