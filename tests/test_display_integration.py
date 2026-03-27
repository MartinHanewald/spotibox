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
