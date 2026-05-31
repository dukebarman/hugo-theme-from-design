from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hugo_theme_check.py"
SPEC = importlib.util.spec_from_file_location("hugo_theme_check", SCRIPT)
hugo_theme_check = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(hugo_theme_check)


def write_png(path: Path, width: int, height: int, *, varied: bool = False) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    rows = []
    for y in range(height):
        pixels = bytearray()
        for x in range(width):
            if varied and (x + y) % 9 == 0:
                pixels.extend((20, 90, 160))
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


class HugoThemeCheckTests(unittest.TestCase):
    def test_has_hugo_config_detects_config_default_hugo_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config" / "_default").mkdir(parents=True)
            (base / "config" / "_default" / "hugo.yaml").write_text("title: Demo\n", encoding="utf-8")

            self.assertTrue(hugo_theme_check.has_hugo_config(base))

    def test_has_hugo_config_detects_root_hugo_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "hugo.json").write_text('{"title":"Demo"}\n', encoding="utf-8")

            self.assertTrue(hugo_theme_check.has_hugo_config(base))

    def test_read_toml_falls_back_without_tomllib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "hugo.toml"
            config.write_text(
                "\n".join(
                    [
                        "defaultContentLanguageInSubdir = true",
                        "[languages.en]",
                        "languageName = 'English'",
                    ]
                ),
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            with mock.patch.object(hugo_theme_check, "tomllib", None):
                data = hugo_theme_check.read_toml(config, result)

            self.assertEqual(result["errors"], [])
            self.assertEqual(result["warnings"], [])
            self.assertTrue(data["defaultContentLanguageInSubdir"])
            self.assertEqual(data["languages"]["en"]["languageName"], "English")

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
            write_png(theme / "images" / "screenshot.png", 1500, 1000, varied=True)
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_preview(result, theme, "screenshot", (1500, 1000))

            self.assertEqual(result["warnings"], [])
            self.assertTrue(any("Pixel sanity check passed" in entry["message"] for entry in result["info"]))

    def test_check_preview_warns_on_blank_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "images").mkdir()
            write_png(theme / "images" / "screenshot.png", 1500, 1000)
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_preview(result, theme, "screenshot", (1500, 1000))

            self.assertTrue(any("appears blank" in warning["message"] for warning in result["warnings"]))

    def test_png_pixel_sanity_rejects_oversized_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "oversized.png"
            write_png(image, 12, 8)
            data = bytearray(image.read_bytes())
            data[16:20] = (20_000).to_bytes(4, "big")
            data[20:24] = (20_000).to_bytes(4, "big")
            image.write_bytes(data)

            ok, message = hugo_theme_check.png_pixel_sanity(image)

        self.assertFalse(ok)
        self.assertIn("too large", message)

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

    def test_partials_state_does_not_treat_empty_directory_as_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            layouts = Path(tmp) / "layouts"
            (layouts / "_partials").mkdir(parents=True)

            kind, path, has_files = hugo_theme_check.partials_state(layouts)

            self.assertEqual(kind, "modern")
            self.assertEqual(path, layouts / "_partials")
            self.assertFalse(has_files)

    def test_multilingual_links_warn_when_link_leaves_language_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            example_site = Path(tmp) / "exampleSite"
            (example_site / "content" / "en" / "posts").mkdir(parents=True)
            (example_site / "content" / "ru" / "posts").mkdir(parents=True)
            (example_site / "hugo.toml").write_text(
                "\n".join(
                    [
                        "defaultContentLanguageInSubdir = true",
                        "[languages.en]",
                        "languageName = 'English'",
                        "[languages.ru]",
                        "languageName = 'Russian'",
                    ]
                ),
                encoding="utf-8",
            )
            (example_site / "content" / "en" / "posts" / "one.md").write_text(
                "[Good](/en/posts/two/) [Bad](/posts/two/) [Asset](/images/a.png)\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_multilingual_links(result, example_site)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("'en' branch", result["warnings"][0]["message"])

    def test_hardcoded_replaceable_images_warns_for_template_literal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "layouts" / "_partials" / "hero.html").write_text(
                '<img src="/images/specific-person-avatar.jpg" alt="">\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_hardcoded_replaceable_images(result, theme)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("hardcoded replaceable image path", result["warnings"][0]["message"])

    def test_hardcoded_replaceable_images_allows_generic_non_personal_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "layouts" / "_partials" / "card.html").write_text(
                '<img src="/images/grid-placeholder.jpg" alt="">\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_hardcoded_replaceable_images(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_footer_theme_attribution_accepts_publication_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "i18n").mkdir()
            (theme / "exampleSite").mkdir()
            (theme / "layouts" / "_partials" / "footer.html").write_text(
                "{{ with .Site.Params.footer }}{{ if .showThemeAttribution }}{{ i18n \"themeAttribution\" . }}{{ end }}{{ end }}\n",
                encoding="utf-8",
            )
            (theme / "i18n" / "en.toml").write_text(
                "[themeAttribution]\nother = 'Theme {{ .themeName }} by {{ .themeAuthorName }}.'\n",
                encoding="utf-8",
            )
            (theme / "exampleSite" / "hugo.toml").write_text(
                "\n".join(
                    [
                        "[params.footer]",
                        "showCopyright = true",
                        "showHugoAttribution = true",
                        "showThemeAttribution = true",
                        "themeName = 'Demo'",
                        "themeURL = 'https://example.org/theme'",
                        "themeAuthorName = 'Author'",
                        "themeAuthorURL = 'https://example.org/author'",
                    ]
                ),
                encoding="utf-8",
            )
            (theme / "README.md").write_text(
                "Set `params.footer.showCopyright`, `showHugoAttribution`, `showThemeAttribution`, `themeName`, `themeURL`, `themeAuthorName`, and `themeAuthorURL`.\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_footer_theme_attribution(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_footer_theme_attribution_warns_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "layouts" / "_partials" / "footer.html").write_text("<footer>Demo</footer>\n", encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_footer_theme_attribution(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertTrue(any("missing footer theme attribution params" in message for message in messages))
            self.assertTrue(any("README should document" in message for message in messages))
            self.assertTrue(any("localizable through i18n" in message for message in messages))
            self.assertTrue(any("layouts should render" in message for message in messages))

    def test_publication_warns_about_theme_root_build_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            for directory in ("archetypes", "assets", "content", "data", "i18n", "layouts", "static", "public"):
                (theme / directory).mkdir(parents=True)
            (theme / "layouts" / "_partials").mkdir()
            (theme / "layouts" / "_partials" / "head.html").write_text("", encoding="utf-8")
            (theme / "layouts" / "home.html").write_text("{{ define \"main\" }}{{ end }}\n", encoding="utf-8")
            (theme / "hugo.yaml").write_text("title: Demo\n", encoding="utf-8")
            (theme / "theme.toml").write_text(
                "\n".join(
                    [
                        "name = 'Demo'",
                        "license = 'MIT'",
                        "licenselink = 'https://example.org/license'",
                        "description = 'Demo theme'",
                        "homepage = 'https://example.org/'",
                        "min_version = '0.146.0'",
                    ]
                ),
                encoding="utf-8",
            )
            argv = ["hugo_theme_check.py", "--theme-dir", str(theme), "--publication", "--skip-build"]
            buffer = io.StringIO()

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(hugo_theme_check.shutil, "which", return_value="/usr/bin/hugo"),
                mock.patch.object(hugo_theme_check, "run_command", return_value=(0, "hugo v0.161.1")),
                contextlib.redirect_stdout(buffer),
            ):
                code = hugo_theme_check.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(any("theme root: public" in warning["message"] for warning in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
