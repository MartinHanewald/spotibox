"""Unified GPIO button controller for Spotibox.

Combines simple single-press buttons and combo-button pairs behind a
single class with proper software debouncing and timing-window-based
combo detection.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from time import monotonic

from gpiozero import Button

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pin assignments (BCM numbering)
# ---------------------------------------------------------------------------
PINS: dict[str, int] = {
    "play1": 4,
    "play2": 27,
    "play3": 22,
    "play4": 5,       # combo pair 1, pin A
    "play5": 6,       # combo pair 1, pin B
    "play6": 13,      # combo pair 2, pin A
    "pause": 26,      # combo pair 2, pin B
    "vol_up": 14,
    "vol_down": 15,
    "next": 12,
}

# Defaults — tunable via constructor
DEBOUNCE_S = 0.3       # ignore repeat presses within this window
COMBO_WINDOW_S = 0.15  # time to wait for second button in combo pair
BOUNCE_TIME_S = 0.05   # gpiozero hardware-level bounce filter


# ---------------------------------------------------------------------------
# Stats tracker
# ---------------------------------------------------------------------------
class ButtonStats:
    """Thread-safe press counter and timing tracker per action."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, int | float]] = {}
        self._lock = threading.Lock()

    def record(self, action: str) -> None:
        now = monotonic()
        with self._lock:
            entry = self._data.setdefault(action, {"count": 0, "last": 0.0})
            entry["count"] += 1
            entry["last"] = now

    def get(self, action: str) -> dict[str, int | float]:
        with self._lock:
            return dict(self._data.get(action, {"count": 0, "last": 0.0}))

    def snapshot(self) -> dict[str, dict[str, int | float]]:
        with self._lock:
            return {k: dict(v) for k, v in self._data.items()}

    def reset(self) -> None:
        with self._lock:
            self._data.clear()


# ---------------------------------------------------------------------------
# Combo pair — two buttons that can fire individually or together
# ---------------------------------------------------------------------------
class _ComboPair:
    """Two GPIO buttons that fire individually or as a combo.

    When one button is pressed, a short timer starts.  If the partner
    button is pressed within ``combo_window_s`` the *both* action fires.
    Otherwise the single-button action fires after the window expires.
    """

    def __init__(
        self,
        pin_a: int,
        pin_b: int,
        action_a: str,
        action_b: str,
        action_both: str,
        fire: Callable[[str], None],
        debounce_s: float = DEBOUNCE_S,
        combo_window_s: float = COMBO_WINDOW_S,
        pin_factory=None,
    ) -> None:
        self._action_a = action_a
        self._action_b = action_b
        self._action_both = action_both
        self._fire = fire
        self._debounce_s = debounce_s
        self._combo_window_s = combo_window_s

        self._lock = threading.Lock()
        self._pending_timer: threading.Timer | None = None
        self._pending_which: str | None = None
        self._pending_time: float = 0.0
        self._last_fire: dict[str, float] = {"a": 0.0, "b": 0.0, "both": 0.0}

        self._btn_a = Button(
            pin_a, pull_up=True, bounce_time=BOUNCE_TIME_S,
            pin_factory=pin_factory,
        )
        self._btn_b = Button(
            pin_b, pull_up=True, bounce_time=BOUNCE_TIME_S,
            pin_factory=pin_factory,
        )

        self._btn_a.when_pressed = lambda: self._on_press("a")
        self._btn_b.when_pressed = lambda: self._on_press("b")

    def _on_press(self, which: str) -> None:
        now = monotonic()
        with self._lock:
            # Partner already pending → combo?
            if self._pending_which is not None and self._pending_which != which:
                elapsed = now - self._pending_time
                self._cancel_pending()
                if elapsed <= self._combo_window_s:
                    if now - self._last_fire["both"] >= self._debounce_s:
                        self._last_fire["both"] = now
                        self._fire(self._action_both)
                    return
                # Window already expired — fire the stale pending single first
                self._do_fire_single(self._pending_which, self._pending_time)

            # Debounce: ignore rapid re-press of the same button
            if now - self._last_fire.get(which, 0.0) < self._debounce_s:
                logger.debug("Debounced combo %s", which)
                return

            # Cancel any leftover pending (e.g. same button pressed twice)
            self._cancel_pending()

            # Start combo window
            self._pending_which = which
            self._pending_time = now
            self._pending_timer = threading.Timer(
                self._combo_window_s, self._on_timeout, args=(which, now),
            )
            self._pending_timer.daemon = True
            self._pending_timer.start()

    def _on_timeout(self, which: str, press_time: float) -> None:
        with self._lock:
            if self._pending_which == which and self._pending_time == press_time:
                self._pending_which = None
                self._pending_timer = None
                self._do_fire_single(which, press_time)

    def _do_fire_single(self, which: str, now: float) -> None:
        self._last_fire[which] = now
        action = self._action_a if which == "a" else self._action_b
        self._fire(action)

    def _cancel_pending(self) -> None:
        if self._pending_timer is not None:
            self._pending_timer.cancel()
        self._pending_timer = None
        self._pending_which = None
        self._pending_time = 0.0

    def close(self) -> None:
        with self._lock:
            self._cancel_pending()
        self._btn_a.close()
        self._btn_b.close()


# ---------------------------------------------------------------------------
# Unified controller
# ---------------------------------------------------------------------------
class SpotiboxButtons:
    """Unified GPIO button controller for the Spotibox player.

    Manages all physical buttons with software debouncing and
    timing-window combo detection for button pairs.

    Parameters
    ----------
    callbacks : dict[str, Callable[[], None]]
        Maps action names to handler functions.  Expected keys:
        ``"album1"`` through ``"album8"``, ``"pause"``,
        ``"vol_up"``, ``"vol_down"``, ``"next"``.
    pin_factory :
        Optional gpiozero pin factory (for testing).
    debounce_s : float
        Seconds to ignore repeated presses of the same button.
    combo_window_s : float
        Seconds to wait for a second button in a combo pair.
    """

    def __init__(
        self,
        callbacks: dict[str, Callable[[], None]],
        pin_factory=None,
        debounce_s: float = DEBOUNCE_S,
        combo_window_s: float = COMBO_WINDOW_S,
    ) -> None:
        self._callbacks = callbacks
        self._stats = ButtonStats()
        self._last_press: dict[int, float] = {}
        self._debounce_s = debounce_s

        # --- Simple buttons ---
        simple_map: list[tuple[int, str]] = [
            (PINS["play1"], "album1"),
            (PINS["play2"], "album2"),
            (PINS["play3"], "album3"),
            (PINS["vol_up"], "vol_up"),
            (PINS["vol_down"], "vol_down"),
            (PINS["next"], "next"),
        ]
        self._buttons: list[Button] = []
        for pin, action in simple_map:
            btn = Button(
                pin, pull_up=True, bounce_time=BOUNCE_TIME_S,
                pin_factory=pin_factory,
            )
            btn.when_pressed = lambda a=action, p=pin: self._on_simple(p, a)
            self._buttons.append(btn)

        # --- Combo button pairs ---
        self._combo1 = _ComboPair(
            pin_a=PINS["play4"],
            pin_b=PINS["play5"],
            action_a="album4",
            action_b="album5",
            action_both="album7",
            fire=self._fire,
            debounce_s=debounce_s,
            combo_window_s=combo_window_s,
            pin_factory=pin_factory,
        )
        self._combo2 = _ComboPair(
            pin_a=PINS["play6"],
            pin_b=PINS["pause"],
            action_a="album6",
            action_b="pause",
            action_both="album8",
            fire=self._fire,
            debounce_s=debounce_s,
            combo_window_s=combo_window_s,
            pin_factory=pin_factory,
        )

        logger.info(
            "SpotiboxButtons initialised — %d simple + 2 combo pairs",
            len(self._buttons),
        )

    # ------------------------------------------------------------------
    # Internal press handling
    # ------------------------------------------------------------------

    def _on_simple(self, pin: int, action: str) -> None:
        now = monotonic()
        if now - self._last_press.get(pin, 0.0) < self._debounce_s:
            logger.debug("Debounced %s on pin %d", action, pin)
            return
        self._last_press[pin] = now
        self._fire(action)

    def _fire(self, action: str) -> None:
        logger.debug("Firing action: %s", action)
        self._stats.record(action)
        cb = self._callbacks.get(action)
        if cb is not None:
            try:
                cb()
            except Exception:
                logger.exception("Error in callback for %s", action)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def stats(self) -> ButtonStats:
        """Access press statistics."""
        return self._stats

    def close(self) -> None:
        """Release all GPIO resources."""
        for btn in self._buttons:
            btn.close()
        self._combo1.close()
        self._combo2.close()
        logger.info("SpotiboxButtons closed")
