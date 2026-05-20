from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_theme_preview.py"
SPEC = importlib.util.spec_from_file_location("render_theme_preview", SCRIPT)
render_theme_preview = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(render_theme_preview)


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
        self.assertIn("--screenshot=/tmp/out.png", command)
        self.assertIn("--window-size=900,600", command)

    def test_run_capture_returns_structured_timeout_failure(self) -> None:
        with mock.patch.object(render_theme_preview.subprocess, "run", side_effect=subprocess.TimeoutExpired(["browser"], 1)):
            code, output = render_theme_preview.run_capture(["browser"], 1)

        self.assertEqual(code, 124)
        self.assertIn("timed out", output)

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
