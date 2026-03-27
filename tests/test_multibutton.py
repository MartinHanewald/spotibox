"""Tests for the MultiButtonBoard class."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_choose_callback_pin1_only():
    """When only pin1 is pressed, callbacks[0] should fire."""
    from spotibox.multibutton import MultiButtonBoard

    cb0, cb1, cb2 = MagicMock(), MagicMock(), MagicMock()

    board = MagicMock(spec=MultiButtonBoard)
    board.callbacks = (cb0, cb1, cb2)

    parent = MagicMock()
    parent.pin1.value = True
    parent.pin2.value = False

    MultiButtonBoard.choose_callback(board, parent)
    cb0.assert_called_once()
    cb1.assert_not_called()
    cb2.assert_not_called()


def test_choose_callback_pin2_only():
    """When only pin2 is pressed, callbacks[1] should fire."""
    from spotibox.multibutton import MultiButtonBoard

    cb0, cb1, cb2 = MagicMock(), MagicMock(), MagicMock()

    board = MagicMock(spec=MultiButtonBoard)
    board.callbacks = (cb0, cb1, cb2)

    parent = MagicMock()
    parent.pin1.value = False
    parent.pin2.value = True

    MultiButtonBoard.choose_callback(board, parent)
    cb0.assert_not_called()
    cb1.assert_called_once()
    cb2.assert_not_called()


def test_choose_callback_both():
    """When both pins are pressed, callbacks[2] should fire."""
    from spotibox.multibutton import MultiButtonBoard

    cb0, cb1, cb2 = MagicMock(), MagicMock(), MagicMock()

    board = MagicMock(spec=MultiButtonBoard)
    board.callbacks = (cb0, cb1, cb2)

    parent = MagicMock()
    parent.pin1.value = True
    parent.pin2.value = True

    MultiButtonBoard.choose_callback(board, parent)
    cb0.assert_not_called()
    cb1.assert_not_called()
    cb2.assert_called_once()


def test_choose_callback_nothing_pressed():
    """When neither pin is pressed, no callback should fire."""
    from spotibox.multibutton import MultiButtonBoard

    cb0, cb1, cb2 = MagicMock(), MagicMock(), MagicMock()

    board = MagicMock(spec=MultiButtonBoard)
    board.callbacks = (cb0, cb1, cb2)

    parent = MagicMock()
    parent.pin1.value = False
    parent.pin2.value = False

    MultiButtonBoard.choose_callback(board, parent)
    cb0.assert_not_called()
    cb1.assert_not_called()
    cb2.assert_not_called()
