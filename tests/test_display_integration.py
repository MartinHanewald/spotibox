"""Integration test for the ILI9341 SPI display on /dev/fb1.

This test writes directly to the framebuffer and verifies the display
is accessible. It requires the physical display to be connected and
the fbtft driver loaded (i.e. /dev/fb1 must exist).

Run with:  uv run pytest tests/test_display_integration.py -v
"""
from __future__ import annotations

import struct
import time
from pathlib import Path

import pytest

FB_DEVICE = Path("/dev/fb1")
WIDTH, HEIGHT = 320, 240
FRAME_SIZE = WIDTH * HEIGHT * 2  # RGB565 = 2 bytes per pixel


def rgb565(r: int, g: int, b: int) -> bytes:
    """Encode an (R, G, B) tuple to a little-endian BGR565 pixel.

    The fbtft driver is loaded with the ``bgr`` flag so the framebuffer
    stores pixels in BGR565 order (blue in the high bits).
    """
    return struct.pack("<H", ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3))


def fill_screen(r: int, g: int, b: int) -> None:
    """Fill the entire framebuffer with a solid colour."""
    FB_DEVICE.write_bytes(rgb565(r, g, b) * (WIDTH * HEIGHT))


# Skip every test in this module when the framebuffer is not available
pytestmark = pytest.mark.skipif(
    not FB_DEVICE.exists(), reason=f"{FB_DEVICE} not found — display not connected"
)


class TestFramebufferAccess:
    """Verify basic read/write access to the ILI9341 framebuffer."""

    def test_fb_device_exists(self):
        assert FB_DEVICE.exists()

    def test_fb_device_is_writable(self):
        assert FB_DEVICE.stat().st_mode & 0o222, f"{FB_DEVICE} is not writable"

    def test_fb_size_matches_resolution(self):
        """The framebuffer size should be 320*240*2 = 153600 bytes (RGB565)."""
        data = FB_DEVICE.read_bytes()
        assert len(data) == FRAME_SIZE


class TestColorOutput:
    """Write colour patterns to the display and verify the framebuffer
    content matches what was written."""

    @pytest.mark.parametrize(
        "name, r, g, b",
        [
            ("red", 255, 0, 0),
            ("green", 0, 255, 0),
            ("blue", 0, 0, 255),
            ("white", 255, 255, 255),
            ("black", 0, 0, 0),
        ],
    )
    def test_solid_fill(self, name, r, g, b):
        fill_screen(r, g, b)
        time.sleep(0.3)
        data = FB_DEVICE.read_bytes()
        expected_pixel = rgb565(r, g, b)
        # Check first, middle, and last pixel
        for offset in [0, FRAME_SIZE // 2, FRAME_SIZE - 2]:
            assert data[offset : offset + 2] == expected_pixel, (
                f"{name}: pixel at offset {offset} mismatch"
            )

    def test_color_bars(self):
        """Write four horizontal colour bars and verify each region."""
        bar_h = HEIGHT // 4
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        buf = b""
        for r, g, b in colors:
            buf += rgb565(r, g, b) * (WIDTH * bar_h)
        FB_DEVICE.write_bytes(buf)
        time.sleep(0.3)

        data = FB_DEVICE.read_bytes()
        for i, (r, g, b) in enumerate(colors):
            mid = (i * bar_h + bar_h // 2) * WIDTH * 2 + WIDTH  # mid-row, mid-col
            assert data[mid : mid + 2] == rgb565(r, g, b), (
                f"bar {i} colour mismatch"
            )

    def teardown_method(self):
        """Clear screen after each test."""
        fill_screen(0, 0, 0)


class TestPygameFramebuffer:
    """Verify pygame can initialise on /dev/fb1."""

    def test_pygame_display_init(self):
        import os
        os.environ["SDL_FBDEV"] = str(FB_DEVICE)

        import pygame
        pygame.display.init()
        info = pygame.display.Info()
        pygame.display.quit()

        assert info.current_w >= WIDTH
        assert info.current_h >= HEIGHT

    def test_display_splash_image(self):
        from PIL import Image as PILImage

        splash_path = Path(__file__).resolve().parent.parent / "assets" / "splash_320x240.png"
        assert splash_path.exists(), f"Splash image not found at {splash_path}"

        # Load, resize, and convert to RGB565 for the framebuffer
        img = PILImage.open(splash_path).convert("RGB").resize((WIDTH, HEIGHT))
        pixels = img.tobytes()

        buf = bytearray(FRAME_SIZE)
        for i in range(WIDTH * HEIGHT):
            off = i * 3
            r, g, b = pixels[off], pixels[off + 1], pixels[off + 2]
            val = ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3)
            struct.pack_into("<H", buf, i * 2, val)

        FB_DEVICE.write_bytes(buf)
        time.sleep(2)

        # Verify the framebuffer is not all-black (image was rendered)
        data = FB_DEVICE.read_bytes()
        assert data != b"\x00" * FRAME_SIZE, "Framebuffer is all black after rendering splash"

        # Clean up
        fill_screen(0, 0, 0)


def _surface_to_fb(surface) -> None:
    """Convert a pygame Surface to BGR565 and write it to the framebuffer.

    SDL2 dropped the legacy ``fbcon`` video driver, so pygame cannot target
    ``/dev/fb1`` directly.  Instead we render into an offscreen surface
    (using real pygame transforms) and push the result to the framebuffer
    ourselves.
    """
    import pygame

    raw = pygame.image.tobytes(surface, "RGB")
    buf = bytearray(FRAME_SIZE)
    for i in range(WIDTH * HEIGHT):
        off = i * 3
        r, g, b = raw[off], raw[off + 1], raw[off + 2]
        struct.pack_into("<H", buf, i * 2, ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3))
    FB_DEVICE.write_bytes(buf)


class TestPygameImageRendering:
    """Render images via the real pygame pipeline and push to /dev/fb1.

    These tests mirror the Spotibox.display_image() flow: open an image
    with Pillow, convert to BMP, load into a pygame surface, scale, and
    blit — then convert the surface to BGR565 and write to the
    framebuffer.  SDL2 has no ``fbcon`` driver, so we bridge the last
    mile manually while exercising the full pygame rendering path.
    """

    ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

    @pytest.fixture(autouse=True)
    def _pygame_session(self):
        """Initialise pygame in offscreen mode and create a screen surface."""
        import os
        os.environ["SDL_VIDEODRIVER"] = "offscreen"

        import pygame
        self.pygame = pygame
        pygame.display.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        yield
        pygame.display.quit()
        fill_screen(0, 0, 0)

    # -- helpers ---------------------------------------------------------

    def _display_image(self, filename: str) -> None:
        """Replicate the Spotibox.display_image() pipeline."""
        from PIL import Image as PILImage

        src = self.ASSETS_DIR / filename
        tmp = self.ASSETS_DIR / "temp.bmp"
        PILImage.open(src).save(tmp)

        picture = self.pygame.image.load(str(tmp))
        psize = picture.get_size()
        scale = HEIGHT / psize[1]
        new_size = (int(psize[0] * scale), int(psize[1] * scale))
        picture = self.pygame.transform.scale(picture, new_size)

        coord = ((WIDTH - new_size[0]) // 2, (HEIGHT - new_size[1]) // 2)
        self.screen.fill((0, 0, 0))
        self.screen.blit(picture, coord)
        _surface_to_fb(self.screen)

    def _read_fb(self) -> bytes:
        return FB_DEVICE.read_bytes()

    # -- tests -----------------------------------------------------------

    def test_pygame_render_splash(self):
        """Render the splash PNG through pygame and verify the framebuffer
        contains non-black pixel data."""
        splash = self.ASSETS_DIR / "splash_320x240.png"
        assert splash.exists(), f"Splash image not found at {splash}"

        self._display_image("splash_320x240.png")
        time.sleep(0.5)

        data = self._read_fb()
        assert data != b"\x00" * FRAME_SIZE, (
            "Framebuffer is all black after pygame render"
        )

    def test_pygame_render_album_art(self):
        """Render a cached album-art JPEG through pygame."""
        jpgs = sorted(self.ASSETS_DIR.glob("*.jpg"))
        if not jpgs:
            pytest.skip("No album-art JPEGs in assets/")

        self._display_image(jpgs[0].name)
        time.sleep(0.5)

        data = self._read_fb()
        assert data != b"\x00" * FRAME_SIZE, (
            "Framebuffer is all black after rendering album art"
        )

    def test_pygame_solid_fill(self):
        """Use pygame to fill the screen with a solid colour and verify the
        framebuffer contains the expected pixel value."""
        self.screen.fill((255, 0, 0))
        _surface_to_fb(self.screen)
        time.sleep(0.3)

        data = self._read_fb()
        expected = rgb565(255, 0, 0)
        # Sample several offsets
        for offset in [0, FRAME_SIZE // 2, FRAME_SIZE - 2]:
            assert data[offset : offset + 2] == expected, (
                f"Pixel at offset {offset} doesn't match red after pygame fill"
            )

    def test_pygame_clear_after_image(self):
        """Render an image then clear to black, confirming the full
        round-trip: pygame render → framebuffer write → read-back."""
        splash = self.ASSETS_DIR / "splash_320x240.png"
        if not splash.exists():
            pytest.skip("Splash image not available")

        self._display_image("splash_320x240.png")
        time.sleep(0.3)

        # Now clear
        self.screen.fill((0, 0, 0))
        _surface_to_fb(self.screen)
        time.sleep(0.3)

        data = self._read_fb()
        assert data == b"\x00" * FRAME_SIZE, (
            "Framebuffer is not all black after pygame clear"
        )
