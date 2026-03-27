#!/usr/bin/env python3
"""GPIO button monitor — logs every button press in real time.

Listens on all configured spotibox GPIO pins and prints which button
was pressed. Uses the same MultiButtonBoard setup as the real app so
that combo presses (both pins simultaneously) are detected correctly.

Press Ctrl+C to exit.

Usage:
    uv run python scripts/monitor_buttons.py
"""
from __future__ import annotations

import signal
import sys
from datetime import datetime

from gpiozero import Button

from spotibox.multibutton import MultiButtonBoard

# Pin assignments (BCM) — must match spotibox/spotibox.py _setup_buttons()
BUTTONPLAY1 = 4
BUTTONPLAY2 = 27
BUTTONPLAY3 = 22
BUTTONPLAY4 = 5    # MultiButtonBoard 1 pin1
BUTTONPLAY5 = 6    # MultiButtonBoard 1 pin2
BUTTONPLAY6 = 13   # MultiButtonBoard 2 pin1
BUTTONPAUSE = 26   # MultiButtonBoard 2 pin2
BUTTONVOLUP = 14
BUTTONVOLDOWN = 15
BUTTONNEXT = 12


def log(action: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"  [{ts}]  {action}")


def main() -> None:
    print("=" * 60)
    print("  Spotibox Button Monitor (with MultiButtonBoard)")
    print("=" * 60)
    print()
    print("  Simple buttons:")
    print(f"    GPIO {BUTTONPLAY1:2d} → PLAY1 (album1)")
    print(f"    GPIO {BUTTONPLAY2:2d} → PLAY2 (album2)")
    print(f"    GPIO {BUTTONPLAY3:2d} → PLAY3 (album3)")
    print(f"    GPIO {BUTTONVOLUP:2d} → VOL UP")
    print(f"    GPIO {BUTTONVOLDOWN:2d} → VOL DOWN")
    print(f"    GPIO {BUTTONNEXT:2d} → NEXT")
    print()
    print("  MultiButtonBoard 1 (GPIO 5 + 6):")
    print(f"    GPIO {BUTTONPLAY4:2d} only  → PLAY4 (album4)")
    print(f"    GPIO {BUTTONPLAY5:2d} only  → PLAY5 (album5)")
    print(f"    both          → PLAY7 (album7)")
    print()
    print("  MultiButtonBoard 2 (GPIO 13 + 26):")
    print(f"    GPIO {BUTTONPLAY6:2d} only  → PLAY6 (album6)")
    print(f"    GPIO {BUTTONPAUSE:2d} only  → PAUSE/RESUME")
    print(f"    both          → PLAY8 (album8)")
    print()
    print("Press any button. Ctrl+C to exit.")
    print("-" * 60)

    # MultiButtonBoard 1: pins 5 + 6
    mlt1 = MultiButtonBoard(
        pin1=BUTTONPLAY4,
        pin2=BUTTONPLAY5,
        bounce_time=0.5,
        callbacks=(
            lambda: log("PLAY4  → album4        (multi1: pin1 only)"),
            lambda: log("PLAY5  → album5        (multi1: pin2 only)"),
            lambda: log("PLAY7  → album7        (multi1: BOTH pins)"),
        ),
    )

    # MultiButtonBoard 2: pins 13 + 26
    mlt2 = MultiButtonBoard(
        pin1=BUTTONPLAY6,
        pin2=BUTTONPAUSE,
        bounce_time=0.5,
        callbacks=(
            lambda: log("PLAY6  → album6        (multi2: pin1 only)"),
            lambda: log("PAUSE  → pause/resume  (multi2: pin2 only)"),
            lambda: log("PLAY8  → album8        (multi2: BOTH pins)"),
        ),
    )

    # Simple buttons
    buttons = []

    def make_simple(pin, name):
        btn = Button(pin, bounce_time=0.05)
        btn.when_pressed = lambda: log(name)
        buttons.append(btn)

    make_simple(BUTTONPLAY1, "PLAY1  → album1")
    make_simple(BUTTONPLAY2, "PLAY2  → album2")
    make_simple(BUTTONPLAY3, "PLAY3  → album3")
    make_simple(BUTTONVOLUP, "VOL UP")
    make_simple(BUTTONVOLDOWN, "VOL DOWN")
    make_simple(BUTTONNEXT, "NEXT")

    # Keep references alive
    _keep = [mlt1, mlt2, *buttons]

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.pause()


if __name__ == "__main__":
    main()
