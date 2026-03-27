#!/usr/bin/env python3
"""Live GPIO button monitor using the unified SpotiboxButtons class.

Listens for all button presses and displays real-time debugging stats
in a continuously-refreshing table.  Useful for verifying hardware
wiring, debounce tuning, and combo detection on the Raspberry Pi.

Usage:
    uv run python scripts/monitor_buttons.py
    uv run python scripts/monitor_buttons.py --debounce 0.4 --combo-window 0.2
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from datetime import datetime
from time import monotonic, sleep

# Ensure the package is importable when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spotibox.buttons import SpotiboxButtons  # noqa: E402

# Ordered list of actions for the display table
ACTIONS = [
    "album1", "album2", "album3",
    "album4", "album5", "album7",
    "album6", "pause", "album8",
    "vol_up", "vol_down", "next",
]

# Human-readable labels
LABELS = {
    "album1":   "PLAY1  (GPIO  4)   album1",
    "album2":   "PLAY2  (GPIO 27)   album2",
    "album3":   "PLAY3  (GPIO 22)   album3",
    "album4":   "PLAY4  (GPIO  5)   album4        [combo1 A]",
    "album5":   "PLAY5  (GPIO  6)   album5        [combo1 B]",
    "album7":   "COMBO1 (GPIO 5+6)  album7        [both]",
    "album6":   "PLAY6  (GPIO 13)   album6        [combo2 A]",
    "pause":    "PAUSE  (GPIO 26)   pause/resume  [combo2 B]",
    "album8":   "COMBO2 (GPIO13+26) album8        [both]",
    "vol_up":   "VOLUP  (GPIO 14)   volume up",
    "vol_down": "VOLDN  (GPIO 15)   volume down",
    "next":     "NEXT   (GPIO 12)   next track",
}

# Recent event log
_event_log: list[str] = []
_log_lock = threading.Lock()
MAX_LOG = 20


def _log_event(action: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"  [{ts}]  {action}"
    with _log_lock:
        _event_log.append(line)
        if len(_event_log) > MAX_LOG:
            _event_log.pop(0)


def _clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _render(btns: SpotiboxButtons, start: float) -> None:
    """Render the stats table and event log."""
    _clear_screen()
    snap = btns.stats.snapshot()
    now = monotonic()

    print("=" * 68)
    print("  Spotibox Button Monitor  —  press Ctrl+C to exit")
    print("=" * 68)
    print()
    print(f"  {'Action':<44s}  {'Count':>5s}  {'Ago':>7s}")
    print(f"  {'-'*44}  {'-'*5}  {'-'*7}")

    for action in ACTIONS:
        label = LABELS.get(action, action)
        info = snap.get(action, {"count": 0, "last": 0.0})
        count = info["count"]
        last = info["last"]
        if last > 0:
            ago = f"{now - last:6.1f}s"
        else:
            ago = "     —"
        # Highlight recently-pressed actions
        marker = " *" if last > 0 and (now - last) < 1.0 else "  "
        print(f"{marker}{label:<44s}  {count:5d}  {ago}")

    print()
    uptime = now - start
    print(f"  Uptime: {uptime:.0f}s   Total presses: "
          f"{sum(s['count'] for s in snap.values())}")
    print()
    print("  — Recent events —")
    with _log_lock:
        if _event_log:
            for line in _event_log:
                print(line)
        else:
            print("  (no events yet)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live GPIO button monitor with debugging stats",
    )
    parser.add_argument(
        "--debounce", type=float, default=0.3,
        help="Software debounce window in seconds (default: 0.3)",
    )
    parser.add_argument(
        "--combo-window", type=float, default=0.15,
        help="Combo detection window in seconds (default: 0.15)",
    )
    parser.add_argument(
        "--refresh", type=float, default=0.25,
        help="Screen refresh interval in seconds (default: 0.25)",
    )
    args = parser.parse_args()

    callbacks: dict[str, object] = {}
    for action in ACTIONS:
        # Capture action in closure
        callbacks[action] = lambda a=action: _log_event(a)

    btns = SpotiboxButtons(
        callbacks,
        debounce_s=args.debounce,
        combo_window_s=args.combo_window,
    )

    start = monotonic()

    def handle_exit(*_):
        btns.close()
        _clear_screen()
        print("Bye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while True:
        _render(btns, start)
        sleep(args.refresh)


if __name__ == "__main__":
    main()
