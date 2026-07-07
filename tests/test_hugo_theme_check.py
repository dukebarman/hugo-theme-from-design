from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import struct
import subprocess
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

    def test_read_toml_warns_on_complex_fallback_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "hugo.toml"
            config.write_text(
                "\n".join(
                    [
                        'description = """Long',
                        'text"""',
                        "[[menu.main]]",
                        'name = "Docs"',
                    ]
                ),
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            with mock.patch.object(hugo_theme_check, "tomllib", None):
                data = hugo_theme_check.read_toml(config, result)

            self.assertEqual(data, {})
            self.assertEqual(result["errors"], [])
            self.assertTrue(any("Complex TOML syntax" in warning["message"] for warning in result["warnings"]))

    def test_run_command_returns_structured_timeout_failure(self) -> None:
        with mock.patch.object(hugo_theme_check.subprocess, "run", side_effect=subprocess.TimeoutExpired(["hugo"], 2)):
            code, output = hugo_theme_check.run_command(["hugo", "version"], Path("/tmp"), 2)

        self.assertEqual(code, 124)
        self.assertIn("Command timed out after 2s", output)

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

    def test_favicon_publication_warns_for_manifest_without_android_icons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "static").mkdir()
            (theme / "static" / "site.webmanifest").write_text('{"name":"Demo"}\n', encoding="utf-8")
            (theme / "README.md").write_text(
                "Demo favicon files can be overridden by placing files with the same names in the site static/ directory.\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_favicon_publication(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertTrue(any("android-chrome-192x192.png" in message for message in messages))
            self.assertTrue(any("android-chrome-512x512.png" in message for message in messages))

    def test_favicon_publication_warns_for_missing_head_link_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "layouts" / "_partials" / "head.html").write_text(
                '<link rel="icon" href="{{ `favicon-32x32.png` | relURL }}" sizes="32x32" />\n',
                encoding="utf-8",
            )
            (theme / "README.md").write_text(
                "Demo favicon files can be overridden by placing files with the same names in the site static/ directory.\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_favicon_publication(result, theme)

            self.assertTrue(any("static/favicon-32x32.png" in warning["message"] for warning in result["warnings"]))

    def test_favicon_publication_warns_when_override_docs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "static").mkdir()
            (theme / "static" / "favicon.ico").write_bytes(b"ico")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_favicon_publication(result, theme)

            self.assertTrue(any("README should document" in warning["message"] for warning in result["warnings"]))

    def test_favicon_publication_accepts_complete_demo_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "static").mkdir()
            (theme / "static" / "favicon.ico").write_bytes(b"ico")
            write_png(theme / "static" / "favicon-16x16.png", 16, 16, varied=True)
            write_png(theme / "static" / "favicon-32x32.png", 32, 32, varied=True)
            write_png(theme / "static" / "apple-touch-icon.png", 180, 180, varied=True)
            write_png(theme / "static" / "android-chrome-192x192.png", 192, 192, varied=True)
            write_png(theme / "static" / "android-chrome-512x512.png", 512, 512, varied=True)
            (theme / "static" / "site.webmanifest").write_text('{"name":"Demo"}\n', encoding="utf-8")
            (theme / "layouts" / "_partials" / "head.html").write_text(
                "\n".join(
                    [
                        '<link rel="icon" href="{{ `favicon.ico` | relURL }}" sizes="any" />',
                        '<link rel="icon" type="image/png" sizes="32x32" href="{{ `favicon-32x32.png` | relURL }}" />',
                        '<link rel="icon" type="image/png" sizes="16x16" href="{{ `favicon-16x16.png` | relURL }}" />',
                        '<link rel="apple-touch-icon" sizes="180x180" href="{{ `apple-touch-icon.png` | relURL }}" />',
                        '<link rel="manifest" href="{{ `site.webmanifest` | relURL }}" />',
                    ]
                ),
                encoding="utf-8",
            )
            (theme / "README.md").write_text(
                "Demo favicon files can be overridden by placing files with the same names in the site static/ directory.\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_favicon_publication(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_telegram_instant_view_ignored_when_not_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts").mkdir()
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_telegram_instant_view_ignores_negative_readme_mention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts").mkdir()
            (theme / "README.md").write_text("What we don't support: Telegram Instant View.\n", encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_telegram_instant_view_warns_for_positive_readme_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts").mkdir()
            (theme / "README.md").write_text("This theme supports Telegram Instant View article templates.\n", encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertTrue(any("data-iv-article" in warning["message"] for warning in result["warnings"]))

    def test_telegram_instant_view_warns_when_declared_but_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "docs").mkdir()
            (theme / "docs" / "telegram-instant-view.tpl").write_text("~version: \"2.1\"\n", encoding="utf-8")
            (theme / "README.md").write_text("Instant View works automatically for articles.\n", encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertTrue(any("data-iv-article" in message for message in messages))
            self.assertTrue(any("data-iv-content" in message for message in messages))
            self.assertTrue(any("data-iv-remove" in message for message in messages))
            self.assertTrue(any("og:type" in message for message in messages))
            self.assertTrue(any("og:image" in message for message in messages))
            self.assertTrue(any("article:published_time" in message for message in messages))
            self.assertTrue(any("official Telegram Instant View documentation" in message for message in messages))
            self.assertTrue(any("should not describe IV as automatic" in message for message in messages))

    def test_telegram_instant_view_warns_when_template_version_not_first_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "docs").mkdir()
            (theme / "docs" / "telegram-instant-view.tpl").write_text(
                "?path: /posts/.+\n~version: \"2.1\"\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertTrue(any("first rule should be" in warning["message"] for warning in result["warnings"]))

    def test_telegram_instant_view_warns_for_raw_datetime_attribute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "docs").mkdir()
            (theme / "docs" / "telegram-instant-view.tpl").write_text(
                '~version: "2.1"\npublished_date: //time[@data-iv-published]/@datetime\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertTrue(any("published_date should use @datetime" in warning["message"] for warning in result["warnings"]))

    def test_telegram_instant_view_warns_for_posts_only_path_in_multilingual_example_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "docs").mkdir()
            (theme / "exampleSite").mkdir()
            (theme / "docs" / "telegram-instant-view.tpl").write_text(
                '~version: "2.1"\n?path: /posts/.+\n',
                encoding="utf-8",
            )
            (theme / "exampleSite" / "hugo.toml").write_text(
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
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertTrue(any("language-prefixed URLs" in warning["message"] for warning in result["warnings"]))

    def test_telegram_instant_view_accepts_publication_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_default").mkdir(parents=True)
            (theme / "docs").mkdir()
            (theme / "layouts" / "_default" / "single.html").write_text(
                "\n".join(
                    [
                        '<article data-iv-article>',
                        '<h1 class="post-title iv-title">{{ .Title }}</h1>',
                        '<time data-iv-published datetime="{{ .Date.Format "2006-01-02T15:04:05Z07:00" }}"></time>',
                        '<figure data-iv-cover></figure>',
                        '<div data-iv-content>{{ .Content }}</div>',
                        '<aside data-iv-remove="true"></aside>',
                        '<meta property="og:type" content="article">',
                        '<meta property="og:image" content="{{ with .Params.images }}{{ index . 0 }}{{ end }}">',
                        '<meta property="article:published_time" content="{{ .Date }}">',
                        "</article>",
                    ]
                ),
                encoding="utf-8",
            )
            (theme / "docs" / "telegram-instant-view.tpl").write_text(
                "~version: \"2.1\"\n?exists: //article[@data-iv-article]\nbody: //*[@data-iv-content]\n",
                encoding="utf-8",
            )
            (theme / "README.md").write_text(
                "Telegram Instant View support prepares HTML and a sample template. Configure and validate it per live domain in Telegram's editor. See https://instantview.telegram.org/docs/.\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_telegram_instant_view(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_subpath_safe_user_paths_warns_for_root_relative_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite" / "content").mkdir(parents=True)
            (theme / "README.md").write_text(
                "Set `heroImage = \"/images/hero.jpg\"`, `postsURL = \"/posts/\"`, and `aboutURL = \"/about\"`.\n",
                encoding="utf-8",
            )
            (theme / "exampleSite" / "hugo.toml").write_text('pageRef = "/tags"\n', encoding="utf-8")
            (theme / "exampleSite" / "content" / "_index.md").write_text(
                "---\nheroImage: /images/about.png\n---\n[Post](/posts/foo/) and body /images/body.png\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_subpath_safe_user_paths(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertEqual(len(messages), 6)
            self.assertTrue(all("root-relative" in message for message in messages))
            self.assertTrue(any("/posts/" in message for message in messages))
            self.assertTrue(any("/about" in message for message in messages))
            self.assertTrue(any("/images/hero.jpg" in message for message in messages))
            self.assertTrue(any("/tags" in message for message in messages))
            self.assertTrue(any("/posts/foo/" in message for message in messages))

    def test_subpath_safe_user_paths_ignores_absolute_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite" / "content").mkdir(parents=True)
            (theme / "exampleSite" / "hugo.toml").write_text(
                'baseURL = "https://example.com/"\n'
                'homepage = "http://example.org/path"\n'
                'cdn = "//cdn.example.org/site.css"\n',
                encoding="utf-8",
            )
            (theme / "README.md").write_text(
                "See https://github.com/dukebarman/dragon-lab.git, <https://instantview.telegram.org/docs>, "
                "mailto:test@example.com, and git@github.com:owner/repo.git.\n",
                encoding="utf-8",
            )
            (theme / "exampleSite" / "content" / "_index.md").write_text(
                "---\nsource: https://example.com/\n---\n[Docs](https://example.com/)\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_subpath_safe_user_paths(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_subpath_safe_user_paths_ignores_example_site_baseurl_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite").mkdir()
            (theme / "exampleSite" / "hugo.toml").write_text('baseURL = "/blog/"\n', encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_subpath_safe_user_paths(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_template_root_url_helpers_warn_for_root_relative_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "layouts" / "_partials" / "hero.html").write_text(
                '<img src="{{ "/images/hero.jpg" | relURL }}" alt="">\n'
                '<a href="{{ relLangURL "/en/tags/" }}">Tags</a>\n'
                '<img src="{{ `images/ok.jpg` | relURL }}" alt="">\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_template_root_url_helpers(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertEqual(len(messages), 2)
            self.assertTrue(any("/images/hero.jpg" in message and "relURL" in message for message in messages))
            self.assertTrue(any("/en/tags/" in message and "relLangURL" in message for message in messages))

    def test_subpath_build_output_warns_for_root_relative_assets_and_internal_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            (destination / "posts").mkdir()
            (destination / "posts" / "index.html").write_text(
                '<link rel="stylesheet" href="/css/site.css"><img src="/images/hero.webp"><a href="/posts/">Post</a>\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_subpath_build_output_assets(result, destination)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertEqual(len(messages), 3)
            self.assertTrue(any('href="/css/site.css"' in message for message in messages))
            self.assertTrue(any('src="/images/hero.webp"' in message for message in messages))
            self.assertTrue(any('href="/posts/"' in message for message in messages))

    def test_theme_head_external_cdns_warns_for_cdn_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_partials").mkdir(parents=True)
            (theme / "layouts" / "_partials" / "head.html").write_text(
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/demo/demo.css">\n'
                '<script src="//unpkg.com/demo/demo.js"></script>\n'
                '<meta property="og:url" content="https://example.com/">\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_theme_head_external_cdns(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertEqual(len(messages), 2)
            self.assertTrue(any("cdn.jsdelivr.net" in message for message in messages))
            self.assertTrue(any("unpkg.com" in message for message in messages))

    def test_example_site_baseurl_warns_unless_example_com(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite").mkdir()
            (theme / "exampleSite" / "hugo.toml").write_text('baseURL = "https://example.org/blog/"\n', encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_example_site_baseurl(result, theme)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("https://example.com/", result["warnings"][0]["message"])

    def test_example_site_baseurl_accepts_example_com(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite").mkdir()
            (theme / "exampleSite" / "hugo.yaml").write_text("baseURL: https://example.com/\n", encoding="utf-8")
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_example_site_baseurl(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_demo_social_links_warns_for_suspicious_demo_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite").mkdir()
            (theme / "exampleSite" / "hugo.toml").write_text(
                "\n".join(
                    [
                        'twitter = "https://example.org/@demo"',
                        'linkedin = "https://www.linkedin.com/in/demo"',
                        'github = "https://github.com/gohugoio/hugo"',
                    ]
                ),
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_demo_social_links(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertEqual(len(messages), 3)
            self.assertTrue(any("example.org/@..." in message for message in messages))
            self.assertTrue(any("LinkedIn" in message for message in messages))
            self.assertTrue(any("github.com/gohugoio/hugo" in message for message in messages))

    def test_demo_asset_sizes_warns_for_large_static_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "static" / "images").mkdir(parents=True)
            large = theme / "static" / "images" / "hero.png"
            large.write_bytes(b"0" * (hugo_theme_check.DEMO_ASSET_SIZE_LIMIT + 1))
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_demo_asset_sizes(result, theme)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("compress large PNG/JPG", result["warnings"][0]["message"])

    def test_safe_code_render_hooks_warns_for_unescaped_safehtml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_markup").mkdir(parents=True)
            (theme / "layouts" / "_markup" / "render-codeblock.html").write_text(
                '<pre data-language="{{ .Type }}"><code>{{ .Inner | safeHTML }}</code></pre>\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_safe_code_render_hooks(result, theme)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("without htmlEscape", result["warnings"][0]["message"])

    def test_safe_code_render_hooks_accepts_html_escape_before_safehtml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts" / "_markup").mkdir(parents=True)
            (theme / "layouts" / "_markup" / "render-codeblock.html").write_text(
                '<pre data-language="{{ .Type }}"><code>{{ .Inner | htmlEscape | safeHTML }}</code></pre>\n',
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_safe_code_render_hooks(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_hugo_deprecations_warns_for_old_template_apis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "layouts").mkdir()
            (theme / "assets" / "scss").mkdir(parents=True)
            (theme / "layouts" / "section.html").write_text("{{ if .IsNode }}Branch{{ end }}\n", encoding="utf-8")
            (theme / "layouts" / "baseof.html").write_text(
                "{{ resources.Get \"scss/main.scss\" | resources.ToCSS }}\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_hugo_deprecations(result, theme)

            messages = [warning["message"] for warning in result["warnings"]]
            self.assertEqual(len(messages), 2)
            self.assertTrue(any(".IsNode" in message for message in messages))
            self.assertTrue(any("resources.ToCSS" in message for message in messages))

    def test_hugo_deprecations_warns_for_global_imaging_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "hugo.toml").write_text(
                "[imaging]\nquality = 82\ncompression = 'lossy'\n[imaging.avif]\nquality = 60\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_hugo_deprecations(result, theme)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("global imaging.quality", result["warnings"][0]["message"])

    def test_hugo_deprecations_accepts_per_format_imaging_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            (theme / "exampleSite").mkdir()
            (theme / "exampleSite" / "hugo.toml").write_text(
                "[imaging]\nanchor = 'smart'\n[imaging.avif]\nquality = 60\nhint = 'photo'\n[imaging.webp]\nquality = 75\n",
                encoding="utf-8",
            )
            result = {"warnings": [], "info": [], "errors": []}

            hugo_theme_check.check_hugo_deprecations(result, theme)

            self.assertEqual(result["warnings"], [])

    def test_subpath_build_warns_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            result = {"warnings": [], "info": [], "errors": []}

            with mock.patch.object(hugo_theme_check, "run_command", return_value=(1, "bad relURL")):
                hugo_theme_check.check_subpath_build(result, (cwd, ["hugo", "--theme", "demo"]), 60)

            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("subpath smoke build failed", result["warnings"][0]["message"])
            self.assertIn(hugo_theme_check.SUBPATH_BASEURL, result["warnings"][0]["message"])

    def test_subpath_build_scans_generated_html_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            result = {"warnings": [], "info": [], "errors": []}

            def fake_run_command(args: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
                destination = Path(args[args.index("--destination") + 1])
                destination.mkdir(parents=True, exist_ok=True)
                (destination / "index.html").write_text('<script src="/js/app.js"></script>\n', encoding="utf-8")
                return 0, "ok"

            with mock.patch.object(hugo_theme_check, "run_command", side_effect=fake_run_command):
                hugo_theme_check.check_subpath_build(result, (cwd, ["hugo", "--theme", "demo"]), 60)

            self.assertTrue(any("subpath smoke build succeeded" in entry["message"] for entry in result["info"]))
            self.assertTrue(any('src="/js/app.js"' in warning["message"] for warning in result["warnings"]))

    def test_publication_main_warns_for_new_publication_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            for directory in ("archetypes", "assets", "content", "data", "i18n", "layouts", "static"):
                (theme / directory).mkdir(parents=True)
            (theme / "layouts" / "_partials").mkdir()
            (theme / "layouts" / "_partials" / "head.html").write_text(
                '<img src="{{ "/images/hero.jpg" | absURL }}" alt="">\n',
                encoding="utf-8",
            )
            (theme / "layouts" / "home.html").write_text("{{ define \"main\" }}{{ end }}\n", encoding="utf-8")
            (theme / "hugo.toml").write_text("title = 'Demo'\n", encoding="utf-8")
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
            (theme / "README.md").write_text('Use `heroImage = "/images/hero.jpg"`.\n', encoding="utf-8")
            (theme / "LICENSE").write_text("MIT\n", encoding="utf-8")
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
        messages = [warning["message"] for warning in payload["warnings"]]
        self.assertTrue(any("user-facing URL" in message for message in messages))
        self.assertTrue(any("template passes root-relative URL" in message for message in messages))

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

    def test_publication_warns_for_apache_without_notice_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            for directory in ("archetypes", "assets", "content", "data", "i18n", "layouts", "static"):
                (theme / directory).mkdir(parents=True)
            (theme / "layouts" / "_partials").mkdir()
            (theme / "layouts" / "_partials" / "head.html").write_text("", encoding="utf-8")
            (theme / "layouts" / "home.html").write_text("{{ define \"main\" }}{{ end }}\n", encoding="utf-8")
            (theme / "hugo.toml").write_text("title = 'Demo'\n", encoding="utf-8")
            (theme / "theme.toml").write_text(
                "\n".join(
                    [
                        "name = 'Demo'",
                        "license = 'Apache-2.0'",
                        "licenselink = 'https://www.apache.org/licenses/LICENSE-2.0'",
                        "description = 'Demo theme'",
                        "homepage = 'https://example.org/'",
                        "min_version = '0.146.0'",
                    ]
                ),
                encoding="utf-8",
            )
            (theme / "README.md").write_text("Demo\n", encoding="utf-8")
            (theme / "LICENSE").write_text("Apache License\n", encoding="utf-8")
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
        self.assertTrue(any("Apache/GPL-style licenses" in warning["message"] for warning in payload["warnings"]))

    def test_publication_accepts_apache_with_notice_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp)
            for directory in ("archetypes", "assets", "content", "data", "i18n", "layouts", "static"):
                (theme / directory).mkdir(parents=True)
            (theme / "layouts" / "_partials").mkdir()
            (theme / "layouts" / "_partials" / "head.html").write_text("", encoding="utf-8")
            (theme / "layouts" / "home.html").write_text("{{ define \"main\" }}{{ end }}\n", encoding="utf-8")
            (theme / "hugo.toml").write_text("title = 'Demo'\n", encoding="utf-8")
            (theme / "theme.toml").write_text(
                "\n".join(
                    [
                        "name = 'Demo'",
                        "license = 'Apache-2.0'",
                        "licenselink = 'https://www.apache.org/licenses/LICENSE-2.0'",
                        "description = 'Demo theme'",
                        "homepage = 'https://example.org/'",
                        "min_version = '0.146.0'",
                    ]
                ),
                encoding="utf-8",
            )
            (theme / "README.md").write_text("Demo\n", encoding="utf-8")
            (theme / "LICENSE").write_text("Apache License\n", encoding="utf-8")
            (theme / "NOTICE").write_text("Copyright 2026 Demo\n", encoding="utf-8")
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
        self.assertFalse(any("Apache/GPL-style licenses" in warning["message"] for warning in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
