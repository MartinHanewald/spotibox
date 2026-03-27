"""Shared test fixtures for the spotibox test suite."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal mock playback state returned by refresh_current()
# ---------------------------------------------------------------------------
MOCK_PLAYBACK = {
    "device": {"volume_percent": 50, "id": "device-123"},
    "context": {"uri": "spotify:album:abc123"},
    "item": {
        "uri": "spotify:track:track1",
        "album": {"total_tracks": 10},
        "track_number": 3,
    },
    "is_playing": True,
    "progress_ms": 12345,
}


def _make_mock_playback(**overrides) -> dict:
    """Return a copy of MOCK_PLAYBACK with optional overrides merged in."""
    import copy
    pb = copy.deepcopy(MOCK_PLAYBACK)
    pb.update(overrides)
    return pb


# ---------------------------------------------------------------------------
# Albums stub
# ---------------------------------------------------------------------------
MOCK_ALBUMS = SimpleNamespace(
    album1="spotify:album:aaa1",
    album2="spotify:album:aaa2",
    album3="spotify:album:aaa3",
    album4="spotify:album:aaa4",
    album5="spotify:album:aaa5",
    album6="spotify:album:aaa6",
    album7="spotify:album:aaa7",
    album8="spotify:playlist:ppp8",
)


# ---------------------------------------------------------------------------
# Fixture: a Spotibox instance with all hardware mocked out
# ---------------------------------------------------------------------------
@pytest.fixture()
def spotibox_instance(tmp_path):
    """Create a Spotibox with pygame, gpiozero, and spotipy fully mocked.

    Patches remain active for the lifetime of the test so that methods like
    ``display_image``, ``display_volume``, etc. don't hit real libraries.
    """
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {
        "devices": [{"id": "device-123", "name": "SPOTIBOX"}]
    }
    mock_sp.current_playback.return_value = _make_mock_playback()
    # Return realistic data from album() so __init__'s get_image() path works
    mock_sp.album.return_value = {
        "artists": [{"name": "Test Artist"}],
        "name": "Test Album",
        "images": [{"url": "https://i.scdn.co/image/test123"}],
    }

    patches = [
        patch("spotibox.spotibox.pygame"),
        patch("spotibox.spotibox.Image"),
        patch("spotibox.spotibox.requests"),
        patch("spotibox.spotibox._load_albums", return_value=MOCK_ALBUMS),
        patch("spotibox.spotibox.spotipy"),
        patch("spotibox.spotibox.ASSETS_DIR", new=tmp_path),
    ]

    mocks = [p.start() for p in patches]
    mock_pygame = mocks[0]
    mock_requests = mocks[2]
    mock_spotipy = mocks[4]

    mock_pygame.display.Info.return_value = SimpleNamespace(
        current_w=320, current_h=240
    )
    mock_spotipy.Spotify.return_value = mock_sp
    mock_requests.get.return_value.content = b"fake-image"

    from spotibox.spotibox import Spotibox

    box = Spotibox(
        client_id="test-id",
        client_secret="test-secret",
        redirect_uri="http://localhost/callback",
        debug=True,
    )

    # Reset call counts from init so tests see a clean slate
    mock_sp.reset_mock()
    mock_sp.current_playback.return_value = _make_mock_playback()
    mock_sp.album.return_value = {
        "artists": [{"name": "Test Artist"}],
        "name": "Test Album",
        "images": [{"url": "https://i.scdn.co/image/test123"}],
    }

    box._mock_sp = mock_sp
    box._mock_pygame = mock_pygame

    yield box

    for p in patches:
        p.stop()
