"""Main module."""
from __future__ import annotations

import importlib.util
import logging
import os
import random
import signal
import subprocess
from pathlib import Path
from time import sleep, time
from types import ModuleType

import pygame
import requests
import spotipy
from gpiozero import LED, Button
from PIL import Image
from requests import ReadTimeout
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from spotibox.multibutton import MultiButtonBoard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEVICE_NAME = "SPOTIBOX"
ALBUMS_PATH = Path("/mnt/albums/albums.py")
ASSETS_DIR = Path("assets")
VOLUME_STEP = 10
IDLE_TIMEOUT = 300   # seconds before idle-shutdown check
FADE_TIMEOUT = 30    # seconds before LED fade
FPS = 30


def _load_albums() -> ModuleType:
    """Load the albums module from the external mount or fall back to the
    bundled copy shipped with the package."""
    if ALBUMS_PATH.is_file():
        spec = importlib.util.spec_from_file_location("albums", str(ALBUMS_PATH))
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    logger.warning(
        "%s not found — falling back to bundled spotibox.albums", ALBUMS_PATH
    )
    from spotibox import albums as mod  # type: ignore[assignment]
    return mod


class Spotibox:
    """Spotibox player with GPIO controls."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        debug: bool = False,
    ) -> None:
        self.albums = _load_albums()

        # Display — target the ILI9341 SPI framebuffer
        os.environ.setdefault("SDL_FBDEV", "/dev/fb1")
        pygame.display.init()
        pygame.mouse.set_visible(False)
        self.displaysize = (
            pygame.display.Info().current_w,
            pygame.display.Info().current_h,
        )
        self.screen = pygame.display.set_mode(self.displaysize, pygame.FULLSCREEN)
        self.display_image("spotibox.PNG")
        self.fps = pygame.time.Clock()

        self.current: dict | None = None
        self.current_image: str | None = None
        self.timer: float = time()
        self.led: LED | None = None
        self.debug = debug

        # Spotify auth
        scope = "user-read-playback-state,user-modify-playback-state"
        self.sp = spotipy.Spotify(
            client_credentials_manager=SpotifyOAuth(
                scope=scope,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
            )
        )

        # Device discovery
        devs = self.sp.devices()
        try:
            self.target_id: str = next(
                d["id"] for d in devs["devices"] if d["name"] == DEVICE_NAME
            )
        except StopIteration:
            available = [d["name"] for d in devs["devices"]]
            raise RuntimeError(
                f"Spotify Connect device '{DEVICE_NAME}' not found. "
                f"Available devices: {available}"
            )

        logger.info("Found device %s at %s.", DEVICE_NAME, self.target_id)

        # Wait for playback state
        while self.current is None:
            self.refresh_current()
            sleep(1)

        logger.debug("Current playback state: %s", self.current)
        if self.current["is_playing"]:
            self.display_image(self.get_image(self.current["context"]["uri"]))
            self.display_track_number()
            self.display_volume()

    # ------------------------------------------------------------------
    # Main event loop — call after __init__ to start the player
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Configure GPIO buttons and enter the main event loop.

        Separated from ``__init__`` so the object can be constructed
        without blocking, e.g. for testing with ``debug=True``.
        """
        if not self.debug:
            self._setup_buttons()

        signal.signal(signal.SIGTERM, self._service_shutdown)
        signal.signal(signal.SIGINT, self._service_shutdown)

        logger.info("Starting main loop")
        try:
            while True:
                timediff = time() - self.timer
                if timediff > IDLE_TIMEOUT:
                    self.timer += 60
                    self.refresh_current()
                    if not self.current["is_playing"]:
                        self.shutdown()

                if timediff > FADE_TIMEOUT:
                    self._display_fade()

                pygame.display.update()
                self.fps.tick(FPS)
        except ServiceExit:
            pygame.display.quit()
            logger.info("Exiting!")

    # ------------------------------------------------------------------
    # Timer / LED helpers
    # ------------------------------------------------------------------

    def reset_timer(self) -> None:
        self.timer = time()
        if self.led is not None:
            self.led.on()

    # ------------------------------------------------------------------
    # Spotify API helpers
    # ------------------------------------------------------------------

    def get_tracklist(self, uid: str) -> list[str] | None:
        try:
            tracks = self.sp.album_tracks(uid)
        except ReadTimeout:
            logger.warning("API not reachable")
            sleep(2)
            return None
        return [t["uri"] for t in tracks["items"]]

    def get_playlist_name(self, uid: str) -> str | None:
        try:
            return self.sp.playlist(uid)["name"]
        except ReadTimeout:
            logger.warning("API not reachable")
            return None

    def get_album_name(self, uid: str) -> str | None:
        try:
            album = self.sp.album(uid)
        except ReadTimeout:
            logger.warning("API not reachable")
            return None
        artist = ", ".join(n["name"] for n in album["artists"])
        return f"{artist} - {album['name']}"

    def get_random_album(self, uid: str) -> str | None:
        try:
            albumlist: list[str] = []
            count = 50
            page = 0
            while count == 50:
                ans = self.sp.artist_albums(
                    uid, album_type="album", limit=50, country="DE", offset=50 * page
                )
                count = len(ans["items"])
                albumlist += [k["uri"] for k in ans["items"]]
                page += 1
        except ReadTimeout:
            logger.warning("API not reachable")
            return None
        return random.choice(albumlist)

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def playback(self, uid: str) -> None:
        if "album" in uid:
            name = self.get_album_name(uid)
        elif "artist" in uid:
            random_album = self.get_random_album(uid)
            if random_album is not None:
                self.playback(random_album)
            return
        elif "playlist" in uid:
            name = self.get_playlist_name(uid)
        else:
            return
        try:
            self.sp.start_playback(device_id=self.target_id, context_uri=uid)
            logger.info("Playing %s", name)
        except ReadTimeout:
            logger.warning("API not reachable")
            return

        image = self.get_image(uid)
        if image is not None:
            self.display_image(image)
        self.current["is_playing"] = True
        self.refresh_current()
        self.display_track_number()
        self.display_volume()
        self.reset_timer()

    def pause_resume(self) -> None:
        try:
            self.refresh_current()
            if self.current["is_playing"]:
                self.pause()
            else:
                self.resume()
        except ReadTimeout:
            logger.warning("API not reachable")
        except TypeError:
            logger.warning("Nothing playing yet.")
        self.reset_timer()

    def pause(self) -> None:
        try:
            self.sp.pause_playback()
            logger.info("Playback paused.")
        except SpotifyException as err:
            logger.warning(err.msg)
        except ReadTimeout:
            logger.warning("API not reachable")

    def resume(self) -> None:
        try:
            self.sp.start_playback(
                device_id=self.current["device"]["id"],
                context_uri=self.current["context"]["uri"],
                offset={"uri": self.current["item"]["uri"]},
                position_ms=self.current["progress_ms"],
            )
        except ReadTimeout:
            logger.warning("API not reachable")
        except SpotifyException as e:
            logger.warning("%s", e)

    def volume_up(self) -> None:
        try:
            current_vol = self.current["device"]["volume_percent"]
            newvol = min(100, current_vol + VOLUME_STEP)
            logger.info("Setting volume to %d", newvol)
            self.sp.volume(newvol)
            self.current["device"]["volume_percent"] = newvol
        except ReadTimeout:
            logger.warning("API not reachable")
            return
        except SpotifyException as e:
            logger.warning("%s", e)
            return
        self.reset_timer()
        self.display_volume()

    def volume_down(self) -> None:
        try:
            current_vol = self.current["device"]["volume_percent"]
            newvol = max(0, current_vol - VOLUME_STEP)
            logger.info("Setting volume to %d", newvol)
            self.sp.volume(newvol)
            self.current["device"]["volume_percent"] = newvol
        except ReadTimeout:
            logger.warning("API not reachable")
            return
        except SpotifyException as e:
            logger.warning("%s", e)
            return
        self.reset_timer()
        self.display_volume()

    def refresh_current(self) -> None:
        try:
            logger.debug("Refreshing current...")
            self.current = self.sp.current_playback()
            if self.current is None:
                logger.debug("Nothing playing, mocking current.")
                self.current = {
                    "device": {"volume_percent": 50, "id": ""},
                    "context": {"uri": ""},
                    "item": {"uri": ""},
                    "is_playing": False,
                    "progress_ms": 0,
                }
        except ReadTimeout:
            logger.warning("API not reachable")
        except SpotifyException as e:
            logger.warning("%s", e)

    def next_track(self) -> None:
        logger.info("Next track...")
        try:
            self.sp.next_track()
        except ReadTimeout:
            logger.warning("API not reachable")
            return
        except SpotifyException as e:
            logger.warning("%s", e)
            return
        self.refresh_current()
        self.display_track_number()
        self.reset_timer()

    # ------------------------------------------------------------------
    # Image / display helpers
    # ------------------------------------------------------------------

    def get_image(self, uid: str) -> str | None:
        try:
            if "album" in uid:
                res = self.sp.album(uid)
            else:
                res = self.sp.playlist(uid)
            images = res.get("images") or []
            if not images:
                logger.warning("No artwork available for %s", uid)
                return None
            fileurl: str = images[0]["url"]
            filename = f"{fileurl.split('/')[-1]}.jpg"
            filepath = ASSETS_DIR / filename
            if not filepath.is_file():
                r = requests.get(fileurl, allow_redirects=True, timeout=10)
                with open(filepath, "wb") as f:
                    f.write(r.content)
        except ReadTimeout:
            logger.warning("API not reachable")
            return None
        except SpotifyException as e:
            logger.warning("%s", e)
            return None
        return filename

    def shutdown(self) -> None:
        logger.info("Shutting down...")
        pygame.display.quit()
        subprocess.run(["sudo", "shutdown", "-f", "now"], check=False)

    def display_image(self, filename: str) -> None:
        src = ASSETS_DIR / filename
        tmp = ASSETS_DIR / "temp.bmp"
        Image.open(src).save(tmp)
        picture = pygame.image.load(str(tmp))
        logger.debug("Displaying %s with size %s", filename, picture.get_size())

        psize = picture.get_size()
        scale = self.displaysize[1] / psize[1]
        psize_new = (int(psize[0] * scale), int(psize[1] * scale))

        picture = pygame.transform.scale(picture, psize_new)
        coord = (
            (self.displaysize[0] - psize_new[0]) // 2,
            (self.displaysize[1] - psize_new[1]) // 2,
        )

        self.screen.fill((0, 0, 0))
        self.screen.blit(picture, coord)
        self.current_image = filename

    # ------------------------------------------------------------------
    # GPIO setup
    # ------------------------------------------------------------------

    def _setup_buttons(self) -> None:
        """Wire GPIO pins to playback handlers."""
        # Pin assignments (BCM numbering)
        LEDPIN = 23
        BUTTONPLAY1 = 4
        BUTTONPLAY2 = 27
        BUTTONPLAY3 = 22
        BUTTONPLAY4 = 5   # MultiButtonBoard 1 pin1
        BUTTONPLAY5 = 6   # MultiButtonBoard 1 pin2
        BUTTONPLAY6 = 13  # MultiButtonBoard 2 pin1
        BUTTONPAUSE = 26  # MultiButtonBoard 2 pin2
        BUTTONVOLUP = 14
        BUTTONVOLDOWN = 15
        BUTTONNEXT = 12
        # Pins 19, 20, 21 are not used.

        albums = self.albums
        self.led = LED(LEDPIN)

        self._mltbtns1 = MultiButtonBoard(
            pin1=BUTTONPLAY4,
            pin2=BUTTONPLAY5,
            bounce_time=0.5,
            callbacks=(
                lambda: self.playback(albums.album4),
                lambda: self.playback(albums.album5),
                lambda: self.playback(albums.album7),
            ),
        )

        self._mltbtns2 = MultiButtonBoard(
            pin1=BUTTONPLAY6,
            pin2=BUTTONPAUSE,
            bounce_time=0.5,
            callbacks=(
                lambda: self.playback(albums.album6),
                self.pause_resume,
                lambda: self.playback(albums.album8),
            ),
        )

        buttonplay1 = Button(BUTTONPLAY1)
        buttonplay1.when_pressed = lambda: self.playback(albums.album1)

        buttonplay2 = Button(BUTTONPLAY2)
        buttonplay2.when_pressed = lambda: self.playback(albums.album2)

        buttonplay3 = Button(BUTTONPLAY3)
        buttonplay3.when_pressed = lambda: self.playback(albums.album3)

        buttonnext = Button(BUTTONNEXT)
        buttonnext.when_pressed = self.next_track

        buttonvolup = Button(BUTTONVOLUP)
        buttonvolup.when_pressed = self.volume_up

        buttonvoldown = Button(BUTTONVOLDOWN)
        buttonvoldown.when_pressed = self.volume_down

        # Keep references so callbacks aren't garbage-collected
        self._buttons = [buttonplay1, buttonplay2, buttonplay3,
                         buttonnext, buttonvolup, buttonvoldown]

        self.reset_timer()

    # ------------------------------------------------------------------
    # Display overlays
    # ------------------------------------------------------------------

    def display_track_number(self) -> None:
        playback = self.current
        context_uri = playback["context"]["uri"]
        if "album" in context_uri:
            total = playback["item"]["album"]["total_tracks"]
            current = playback["item"]["track_number"]
        else:
            try:
                playlist = self.sp.playlist(context_uri)
            except ReadTimeout:
                logger.warning("API not reachable")
                return
            pl_tracks = [i["track"]["uri"] for i in playlist["tracks"]["items"]]
            pb_track = playback["item"]["uri"]
            total = len(pl_tracks)
            current = pl_tracks.index(pb_track) + 1

        self._remove_boxes("left")
        self._draw_boxes(total, current, "left")

    def display_volume(self) -> None:
        current_vol = self.current["device"]["volume_percent"]
        self._remove_boxes("right")
        self._draw_boxes(10, int(current_vol / 10), "right")

    def clear_screen(self) -> None:
        self.screen.fill((0, 0, 0))
        if self.current_image is not None:
            self.display_image(self.current_image)

    def _display_fade(self) -> None:
        if self.led is not None and self.led.value > 0:
            self.led.off()

    def _draw_boxes(self, n: int, active: int, side: str = "left") -> None:
        BASE = (50, 50, 50)
        ACTIVE = (150, 100, 250)
        X = 10 if side == "left" else 290
        screen_h = 240
        box = screen_h / n
        margin = max(int(0.1 * box), 1)
        h = box - 2 * margin

        for k in range(n):
            color = BASE if k >= active else ACTIVE
            pygame.draw.rect(
                self.screen, color, (X, screen_h - h - margin - box * k, 20, h)
            )

    def _remove_boxes(self, side: str = "left") -> None:
        X = 10 if side == "left" else 290
        pygame.draw.rect(self.screen, (0, 0, 0), (X, 0, 20, 240))

    # ------------------------------------------------------------------
    # Shutdown / signal handling
    # ------------------------------------------------------------------

    def _service_shutdown(self, signum: int, frame) -> None:
        logger.info("Caught signal %d", signum)
        raise ServiceExit


class ServiceExit(Exception):
    """Custom exception to trigger clean exit of the main loop."""
