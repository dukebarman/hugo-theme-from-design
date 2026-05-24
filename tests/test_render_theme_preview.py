from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zlib
import struct
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_theme_preview.py"
SPEC = importlib.util.spec_from_file_location("render_theme_preview", SCRIPT)
render_theme_preview = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(render_theme_preview)


def write_png(path: Path, width: int, height: int, *, varied: bool = False) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    rows = []
    for y in range(height):
        pixels = bytearray()
        for x in range(width):
            if varied and (x + y) % 5 == 0:
                pixels.extend((12, 80, 150))
            else:
                pixels.extend((255, 255, 255))
        rows.append(b"\x00" + bytes(pixels))
    raw = b"".join(rows)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(data)


class FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type

    def get(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return self.content_type
        return default


class FakeResponse:
    def __init__(self, url: str, body: bytes, content_type: str = "text/html") -> None:
        self.url = url
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, _size: int) -> bytes:
        return self.body


class RenderThemePreviewTests(unittest.TestCase):
    def test_parse_size_accepts_width_x_height(self) -> None:
        self.assertEqual(render_theme_preview.parse_size("1500x1000"), (1500, 1000))

    def test_parse_size_rejects_invalid_values(self) -> None:
        with self.assertRaises(Exception):
            render_theme_preview.parse_size("0x1000")
        with self.assertRaises(Exception):
            render_theme_preview.parse_size("wide")

    def test_detect_browser_respects_auto_order(self) -> None:
        def fake_resolve(candidate: str) -> Path | None:
            if candidate == "google-chrome":
                return Path("/usr/bin/google-chrome")
            return None

        with mock.patch.object(render_theme_preview, "resolve_executable", side_effect=fake_resolve):
            self.assertEqual(render_theme_preview.detect_browser("auto"), ("chrome", Path("/usr/bin/google-chrome")))

    def test_browser_command_uses_firefox_profile(self) -> None:
        command = render_theme_preview.browser_command(
            "firefox",
            Path("/usr/bin/firefox"),
            "http://127.0.0.1:1313/",
            Path("/tmp/out.png"),
            (900, 600),
            Path("/tmp/profile"),
        )

        self.assertIn("--profile", command)
        self.assertIn("/tmp/profile", command)
        self.assertEqual(command[-1], "http://127.0.0.1:1313/")

    def test_browser_command_uses_chrome_screenshot_flag(self) -> None:
        command = render_theme_preview.browser_command(
            "chrome",
            Path("/usr/bin/google-chrome"),
            "http://127.0.0.1:1313/",
            Path("/tmp/out.png"),
            (900, 600),
            None,
        )

        self.assertIn("--headless=new", command)
        self.assertIn("--virtual-time-budget=3000", command)
        self.assertIn("--screenshot=/tmp/out.png", command)
        self.assertIn("--window-size=900,600", command)

    def test_run_capture_returns_structured_timeout_failure(self) -> None:
        with mock.patch.object(render_theme_preview.subprocess, "run", side_effect=subprocess.TimeoutExpired(["browser"], 1)):
            code, output = render_theme_preview.run_capture(["browser"], 1)

        self.assertEqual(code, 124)
        self.assertIn("timed out", output)

    def test_resolve_preview_url_uses_same_origin_canonical_from_root(self) -> None:
        body = b'<html><head><link rel="canonical" href="/en/"></head></html>'
        with mock.patch.object(render_theme_preview.urllib.request, "urlopen", return_value=FakeResponse("http://127.0.0.1:1313/", body)):
            url, info, warnings = render_theme_preview.resolve_preview_url("http://127.0.0.1:1313/", 1)

        self.assertEqual(url, "http://127.0.0.1:1313/en/")
        self.assertTrue(any("Canonical URL" in message for message in info))
        self.assertEqual(warnings, [])

    def test_resolve_preview_url_uses_same_origin_meta_refresh(self) -> None:
        body = b'<html><head><meta http-equiv="refresh" content="0; url=/ru/"></head></html>'
        with mock.patch.object(render_theme_preview.urllib.request, "urlopen", return_value=FakeResponse("http://127.0.0.1:1313/", body)):
            url, _info, warnings = render_theme_preview.resolve_preview_url("http://127.0.0.1:1313/", 1)

        self.assertEqual(url, "http://127.0.0.1:1313/ru/")
        self.assertEqual(warnings, [])

    def test_png_pixel_sanity_rejects_blank_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "blank.png"
            write_png(image, 12, 8)

            ok, message = render_theme_preview.png_pixel_sanity(image)

        self.assertFalse(ok)
        self.assertIn("appears blank", message)

    def test_png_pixel_sanity_accepts_varied_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "varied.png"
            write_png(image, 12, 8, varied=True)

            ok, message = render_theme_preview.png_pixel_sanity(image)

        self.assertTrue(ok)
        self.assertIn("Pixel sanity check passed", message)

    def test_main_reports_missing_browser_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "render_theme_preview.py",
                "--url",
                "http://127.0.0.1:1313/",
                "--theme-dir",
                tmp,
            ]
            buffer = io.StringIO()
            with mock.patch.object(sys, "argv", argv), mock.patch.object(render_theme_preview, "detect_browser", return_value=None), contextlib.redirect_stdout(buffer):
                code = render_theme_preview.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("No supported headless browser", payload["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
