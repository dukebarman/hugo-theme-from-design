from __future__ import annotations

import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hugo_theme_check.py"
SPEC = importlib.util.spec_from_file_location("hugo_theme_check", SCRIPT)
hugo_theme_check = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(hugo_theme_check)


def write_png(path: Path, width: int, height: int) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    raw = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(data)


class HugoThemeCheckTests(unittest.TestCase):
    def test_has_hugo_config_detects_config_default_hugo_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config" / "_default").mkdir(parents=True)
            (base / "config" / "_default" / "hugo.toml").write_text("title = 'Demo'\n", encoding="utf-8")

            self.assertTrue(hugo_theme_check.has_hugo_config(base))

    def test_classify_root_content_support_vs_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            (content / "search").mkdir(parents=True)
            (content / "posts").mkdir(parents=True)
            support_search = content / "search" / "_index.md"
            support_manifest = content / "manifest.md"
            sample_post = content / "posts" / "demo.md"

            self.assertEqual(hugo_theme_check.classify_root_content(support_search, content), "support")
            self.assertEqual(hugo_theme_check.classify_root_content(support_manifest, content), "support")
            self.assertEqual(hugo_theme_check.classify_root_content(sample_post, content), "sample")

    def test_image_size_reads_png_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "sample.png"
            write_png(image, 1500, 1000)

            self.assertEqual(hugo_theme_check.image_size(image), (1500, 1000))

    def test_check_preview_accepts_expected_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "images").mkdir()
            write_png(theme / "images" / "screenshot.png", 1500, 1000)
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_preview(result, theme, "screenshot", (1500, 1000))

            self.assertEqual(result["warnings"], [])
            self.assertEqual(len(result["info"]), 1)

    def test_check_preview_warns_on_missing_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_preview(result, Path(tmp), "tn", (900, 600))

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("Missing images/tn", result["warnings"][0]["message"])

    def test_detect_build_command_prefers_example_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            theme = root / "themes" / "demo"
            (theme / "exampleSite").mkdir(parents=True)

            cwd, command = hugo_theme_check.detect_build_command(theme, None)

            self.assertEqual(cwd, theme / "exampleSite")
            self.assertEqual(command, ["hugo", "--themesDir", str(theme.parent), "--theme", "demo"])

    def test_detect_build_command_uses_site_theme_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            theme = site / "themes" / "demo"
            theme.mkdir(parents=True)

            cwd, command = hugo_theme_check.detect_build_command(theme, site)

            self.assertEqual(cwd, site)
            self.assertEqual(command, ["hugo", "--theme", "demo"])


if __name__ == "__main__":
    unittest.main()
