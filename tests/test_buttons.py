"""Tests for the unified SpotiboxButtons controller."""
from __future__ import annotations

import threading
from time import sleep
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake Button that records when_pressed callbacks for manual triggering
# ---------------------------------------------------------------------------
class FakeButton:
    """Minimal stand-in for gpiozero.Button used in tests."""

    instances: list[FakeButton] = []

    def __init__(self, pin, *, pull_up=True, bounce_time=None, pin_factory=None):
        self.pin_num = pin
        self._when_pressed = None
        FakeButton.instances.append(self)

    @property
    def when_pressed(self):
        return self._when_pressed

    @when_pressed.setter
    def when_pressed(self, value):
        self._when_pressed = value

    def press(self):
        """Simulate a button press."""
        if self._when_pressed is not None:
            self._when_pressed()

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _clear_fake_instances():
    FakeButton.instances.clear()
    yield
    FakeButton.instances.clear()


@pytest.fixture()
def patched_button():
    """Patch gpiozero.Button in the buttons module with FakeButton."""
    with patch("spotibox.buttons.Button", FakeButton):
        yield


def _btn_for_pin(pin: int) -> FakeButton:
    """Find the FakeButton instance wired to a given GPIO pin."""
    return next(b for b in FakeButton.instances if b.pin_num == pin)


def _make_callbacks() -> dict[str, MagicMock]:
    """Return a dict of MagicMock callbacks for every expected action."""
    actions = [
        "album1", "album2", "album3", "album4", "album5",
        "album6", "album7", "album8", "pause",
        "vol_up", "vol_down", "next",
    ]
    return {a: MagicMock(name=f"cb_{a}") for a in actions}


# ===================================================================
# Simple button tests
# ===================================================================

class TestSimpleButtons:

    def test_each_simple_button_fires_correct_action(self, patched_button):
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0)

        pin_action = [
            (PINS["play1"], "album1"),
            (PINS["play2"], "album2"),
            (PINS["play3"], "album3"),
            (PINS["vol_up"], "vol_up"),
            (PINS["vol_down"], "vol_down"),
            (PINS["next"], "next"),
        ]
        for pin, action in pin_action:
            _btn_for_pin(pin).press()
            cbs[action].assert_called_once()

        btns.close()

    def test_debounce_blocks_rapid_repeat(self, patched_button):
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.5)

        pin4 = _btn_for_pin(PINS["play1"])
        pin4.press()
        pin4.press()  # should be debounced
        pin4.press()  # should be debounced

        cbs["album1"].assert_called_once()
        btns.close()

    def test_debounce_allows_after_window(self, patched_button):
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.05)

        pin4 = _btn_for_pin(PINS["play1"])
        pin4.press()
        assert cbs["album1"].call_count == 1

        sleep(0.08)  # wait past debounce window
        pin4.press()
        assert cbs["album1"].call_count == 2

        btns.close()

    def test_stats_recorded_for_simple(self, patched_button):
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0)

        _btn_for_pin(PINS["play1"]).press()
        _btn_for_pin(PINS["play1"]).press()
        _btn_for_pin(PINS["next"]).press()

        snap = btns.stats.snapshot()
        assert snap["album1"]["count"] == 2
        assert snap["next"]["count"] == 1

        btns.close()


# ===================================================================
# Combo pair tests
# ===================================================================

class TestComboPair:

    def test_single_a_fires_after_window(self, patched_button):
        """Pressing only pin_a should fire action_a after combo window."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.05)

        _btn_for_pin(PINS["play4"]).press()
        # Action shouldn't fire immediately — combo window still open
        cbs["album4"].assert_not_called()

        sleep(0.1)  # wait for combo window to expire
        cbs["album4"].assert_called_once()
        cbs["album5"].assert_not_called()
        cbs["album7"].assert_not_called()

        btns.close()

    def test_single_b_fires_after_window(self, patched_button):
        """Pressing only pin_b should fire action_b after combo window."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.05)

        _btn_for_pin(PINS["play5"]).press()
        sleep(0.1)

        cbs["album5"].assert_called_once()
        cbs["album4"].assert_not_called()
        cbs["album7"].assert_not_called()

        btns.close()

    def test_combo_both_pressed_within_window(self, patched_button):
        """Pressing both pins within the combo window fires the combo action."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.2)

        _btn_for_pin(PINS["play4"]).press()
        sleep(0.02)
        _btn_for_pin(PINS["play5"]).press()

        # Combo should fire immediately
        cbs["album7"].assert_called_once()
        cbs["album4"].assert_not_called()
        cbs["album5"].assert_not_called()

        btns.close()

    def test_combo_reversed_order(self, patched_button):
        """Combo fires regardless of which pin is pressed first."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.2)

        _btn_for_pin(PINS["play5"]).press()
        sleep(0.02)
        _btn_for_pin(PINS["play4"]).press()

        cbs["album7"].assert_called_once()
        cbs["album4"].assert_not_called()
        cbs["album5"].assert_not_called()

        btns.close()

    def test_combo2_pause_single(self, patched_button):
        """Pause button (combo pair 2, pin_b) fires alone after window."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.05)

        _btn_for_pin(PINS["pause"]).press()
        sleep(0.1)

        cbs["pause"].assert_called_once()
        cbs["album6"].assert_not_called()
        cbs["album8"].assert_not_called()

        btns.close()

    def test_combo2_both_fires_album8(self, patched_button):
        """Pressing play6 + pause together fires album8."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.2)

        _btn_for_pin(PINS["play6"]).press()
        sleep(0.02)
        _btn_for_pin(PINS["pause"]).press()

        cbs["album8"].assert_called_once()
        cbs["album6"].assert_not_called()
        cbs["pause"].assert_not_called()

        btns.close()

    def test_combo_debounce(self, patched_button):
        """Rapid double combo presses are debounced."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.5, combo_window_s=0.2)

        # First combo
        _btn_for_pin(PINS["play4"]).press()
        sleep(0.02)
        _btn_for_pin(PINS["play5"]).press()
        cbs["album7"].assert_called_once()

        # Rapid second combo — should be debounced
        sleep(0.05)
        _btn_for_pin(PINS["play4"]).press()
        sleep(0.02)
        _btn_for_pin(PINS["play5"]).press()

        sleep(0.3)  # let any timers settle
        assert cbs["album7"].call_count == 1

        btns.close()

    def test_outside_window_fires_single(self, patched_button):
        """Pressing the second button after the window fires two singles."""
        from spotibox.buttons import PINS, SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0, combo_window_s=0.05)

        _btn_for_pin(PINS["play4"]).press()
        sleep(0.1)  # past combo window — single fires
        cbs["album4"].assert_called_once()

        _btn_for_pin(PINS["play5"]).press()
        sleep(0.1)
        cbs["album5"].assert_called_once()
        cbs["album7"].assert_not_called()

        btns.close()


# ===================================================================
# ButtonStats tests
# ===================================================================

class TestButtonStats:

    def test_record_and_get(self):
        from spotibox.buttons import ButtonStats

        stats = ButtonStats()
        stats.record("vol_up")
        stats.record("vol_up")
        stats.record("next")

        assert stats.get("vol_up")["count"] == 2
        assert stats.get("next")["count"] == 1
        assert stats.get("unknown")["count"] == 0

    def test_snapshot(self):
        from spotibox.buttons import ButtonStats

        stats = ButtonStats()
        stats.record("a")
        stats.record("b")

        snap = stats.snapshot()
        assert "a" in snap
        assert "b" in snap
        assert snap["a"]["count"] == 1

    def test_reset(self):
        from spotibox.buttons import ButtonStats

        stats = ButtonStats()
        stats.record("x")
        stats.reset()
        assert stats.snapshot() == {}


# ===================================================================
# close() tests
# ===================================================================

class TestClose:

    def test_close_releases_all(self, patched_button):
        from spotibox.buttons import SpotiboxButtons

        cbs = _make_callbacks()
        btns = SpotiboxButtons(cbs, debounce_s=0.0)
        # Should not raise
        btns.close()

    def test_missing_callback_does_not_raise(self, patched_button):
        """Pressing a button whose action has no callback is silently ignored."""
        from spotibox.buttons import PINS, SpotiboxButtons

        btns = SpotiboxButtons({}, debounce_s=0.0)  # no callbacks at all
        _btn_for_pin(PINS["play1"]).press()  # should not raise
        btns.close()
