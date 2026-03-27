"""Tests for the Spotibox class."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from requests import ReadTimeout
from spotipy.exceptions import SpotifyException


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

def test_device_not_found_raises():
    """Spotibox should raise RuntimeError when device is missing."""
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [{"id": "x", "name": "OTHER"}]}

    from types import SimpleNamespace
    with (
        patch("spotibox.spotibox.pygame") as mock_pygame,
        patch("spotibox.spotibox.Image"),
        patch("spotibox.spotibox._load_albums"),
        patch("spotibox.spotibox.spotipy") as mock_spotipy,
    ):
        mock_pygame.display.Info.return_value = SimpleNamespace(
            current_w=320, current_h=240
        )
        mock_spotipy.Spotify.return_value = mock_sp

        from spotibox.spotibox import Spotibox
        with pytest.raises(RuntimeError, match="SPOTIBOX"):
            Spotibox(client_id="id", client_secret="sec",
                     redirect_uri="http://x", debug=True)


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------

def test_volume_up_clamps_at_100(spotibox_instance):
    """volume_up should never exceed 100."""
    box = spotibox_instance
    box.current["device"]["volume_percent"] = 95
    box.volume_up()
    box._mock_sp.volume.assert_called_once_with(100)
    assert box.current["device"]["volume_percent"] == 100


def test_volume_up_from_zero(spotibox_instance):
    box = spotibox_instance
    box.current["device"]["volume_percent"] = 0
    box.volume_up()
    box._mock_sp.volume.assert_called_once_with(10)


def test_volume_down_clamps_at_0(spotibox_instance):
    """volume_down should never go below 0."""
    box = spotibox_instance
    box.current["device"]["volume_percent"] = 5
    box.volume_down()
    box._mock_sp.volume.assert_called_once_with(0)
    assert box.current["device"]["volume_percent"] == 0


def test_volume_down_from_100(spotibox_instance):
    box = spotibox_instance
    box.current["device"]["volume_percent"] = 100
    box.volume_down()
    box._mock_sp.volume.assert_called_once_with(90)


# ---------------------------------------------------------------------------
# Playback routing
# ---------------------------------------------------------------------------

def test_playback_album(spotibox_instance):
    box = spotibox_instance
    box._mock_sp.album.return_value = {
        "artists": [{"name": "Artist"}],
        "name": "Album",
        "images": [{"url": "https://i.scdn.co/image/abc123"}],
    }
    box.playback("spotify:album:xyz")
    box._mock_sp.start_playback.assert_called_once_with(
        device_id="device-123", context_uri="spotify:album:xyz"
    )


def test_playback_playlist(spotibox_instance):
    box = spotibox_instance
    box._mock_sp.playlist.return_value = {
        "name": "My Playlist",
        "images": [{"url": "https://i.scdn.co/image/abc123"}],
        "tracks": {"items": []},
    }
    box.playback("spotify:playlist:xyz")
    box._mock_sp.start_playback.assert_called_once_with(
        device_id="device-123", context_uri="spotify:playlist:xyz"
    )


def test_playback_artist_picks_random_album(spotibox_instance):
    """Artist URI should resolve to a random album, then play it."""
    box = spotibox_instance
    box._mock_sp.artist_albums.return_value = {
        "items": [{"uri": "spotify:album:random1"}]
    }
    box._mock_sp.album.return_value = {
        "artists": [{"name": "A"}],
        "name": "B",
        "images": [{"url": "https://i.scdn.co/image/x"}],
    }
    box.playback("spotify:artist:art1")
    box._mock_sp.start_playback.assert_called_once_with(
        device_id="device-123", context_uri="spotify:album:random1"
    )


# ---------------------------------------------------------------------------
# Pause / resume
# ---------------------------------------------------------------------------

def test_pause(spotibox_instance):
    box = spotibox_instance
    box.pause()
    box._mock_sp.pause_playback.assert_called_once()


def test_resume(spotibox_instance):
    box = spotibox_instance
    box.resume()
    box._mock_sp.start_playback.assert_called_once()


def test_pause_resume_toggles(spotibox_instance):
    box = spotibox_instance
    box.current["is_playing"] = True
    box.pause_resume()
    box._mock_sp.pause_playback.assert_called_once()


# ---------------------------------------------------------------------------
# refresh_current
# ---------------------------------------------------------------------------

def test_refresh_current_nothing_playing(spotibox_instance):
    """When API returns None, a mock playback dict should be set."""
    box = spotibox_instance
    box._mock_sp.current_playback.return_value = None
    box.refresh_current()
    assert box.current is not None
    assert box.current["is_playing"] is False
    assert box.current["device"]["volume_percent"] == 50


def test_refresh_current_on_timeout(spotibox_instance):
    """On timeout, self.current should remain unchanged."""
    box = spotibox_instance
    original = box.current
    box._mock_sp.current_playback.side_effect = ReadTimeout()
    box.refresh_current()
    assert box.current is original


# ---------------------------------------------------------------------------
# next_track
# ---------------------------------------------------------------------------

def test_next_track(spotibox_instance):
    box = spotibox_instance
    box.next_track()
    box._mock_sp.next_track.assert_called_once()


# ---------------------------------------------------------------------------
# get_image
# ---------------------------------------------------------------------------

def test_get_image_no_artwork(spotibox_instance):
    """Should return None when no images are available."""
    box = spotibox_instance
    box._mock_sp.album.return_value = {"images": []}
    result = box.get_image("spotify:album:xyz")
    assert result is None


def test_get_image_caches_file(spotibox_instance, tmp_path, monkeypatch):
    """Image should be downloaded only if not already cached."""
    import spotibox.spotibox as mod
    monkeypatch.setattr(mod, "ASSETS_DIR", tmp_path)

    box = spotibox_instance
    box._mock_sp.album.return_value = {
        "images": [{"url": "https://i.scdn.co/image/abc123"}]
    }

    with patch("spotibox.spotibox.requests") as mock_requests:
        mock_requests.get.return_value.content = b"fake-image-data"
        filename = box.get_image("spotify:album:xyz")
        assert filename == "abc123.jpg"
        assert (tmp_path / "abc123.jpg").exists()
        mock_requests.get.assert_called_once()

        # Second call should use cache, no new download
        filename2 = box.get_image("spotify:album:xyz")
        assert filename2 == "abc123.jpg"
        assert mock_requests.get.call_count == 1


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

def test_shutdown_calls_subprocess(spotibox_instance):
    box = spotibox_instance
    with patch("spotibox.spotibox.subprocess") as mock_sub:
        box.shutdown()
        mock_sub.run.assert_called_once_with(
            ["sudo", "shutdown", "-f", "now"], check=False
        )
