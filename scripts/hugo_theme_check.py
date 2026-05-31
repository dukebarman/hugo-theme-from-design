#!/usr/bin/env python3
"""Structural and smoke-build checks for Hugo themes."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


REQUIRED_DIRS = ["archetypes", "assets", "content", "data", "i18n", "layouts", "static"]
PORT_REQUIRED_DIRS = ["archetypes", "assets", "layouts", "static"]
THEMES_SITE_REQUIRED_META = ["name", "license", "licenselink", "description", "homepage"]
BUILD_ARTIFACTS = ["public", ".hugo_build.lock", "resources"]
CONFIG_FILES = ("hugo.toml", "hugo.yaml", "hugo.yml", "hugo.json", "config.toml", "config.yaml", "config.yml", "config.json")
CONFIG_DIR_FILES = (
    "config/_default/hugo.toml",
    "config/_default/hugo.yaml",
    "config/_default/hugo.yml",
    "config/_default/hugo.json",
    "config/_default/config.toml",
    "config/_default/config.yaml",
    "config/_default/config.yml",
    "config/_default/config.json",
)
README_FILES = ["README.md", "README.markdown", "README"]
LICENSE_FILES = ["LICENSE", "LICENSE.md", "COPYING"]
ROOT_SUPPORT_CONTENT_DIRS = {"search"}
ROOT_SUPPORT_CONTENT_FILES = {"manifest.md"}
FAVICON_CANDIDATES = [
    "static/favicon.ico",
    "static/favicon.svg",
    "assets/icons/favicon.ico",
    "assets/icons/favicon.svg",
    "assets/icons/site.webmanifest",
]
MAX_PREVIEW_IMAGE_BYTES = 25 * 1024 * 1024
MAX_PREVIEW_PIXELS = 12_000_000
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CONTENT_ASSET_SUFFIXES = {
    ".avif",
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".pdf",
    ".png",
    ".svg",
    ".webp",
    ".zip",
}
TEXT_FILE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".md",
    ".scss",
    ".sass",
    ".toml",
    ".ts",
    ".yaml",
    ".yml",
}
HARDCODED_IMAGE_PATH_RE = re.compile(r"""["'`](/images/[^"'`\s)]+\.(?:avif|jpe?g|png|webp))""", re.IGNORECASE)
REPLACEABLE_IMAGE_HINTS = ("hero", "about", "avatar", "profile", "portrait", "headshot", "person", "author")
FOOTER_ATTRIBUTION_KEYS = (
    "showCopyright",
    "showHugoAttribution",
    "showThemeAttribution",
    "themeName",
    "themeURL",
    "themeAuthorName",
    "themeAuthorURL",
)
FOOTER_ATTRIBUTION_I18N_HINTS = (
    "themeAttribution",
    "theme_attribution",
    "footerThemeAttribution",
    "footer_theme_attribution",
)


def add(result: dict, level: str, message: str, path: Path | None = None) -> None:
    entry = {"message": message}
    if path is not None:
        entry["path"] = str(path)
    result[level].append(entry)


def parse_basic_toml_value(value: str) -> object:
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    return value


def parse_basic_toml(text: str) -> dict:
    data: dict = {}
    current = data
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = data
            for part in line[1:-1].split("."):
                current = current.setdefault(part.strip(), {})
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key.strip()] = parse_basic_toml_value(value)
    return data


def read_toml(path: Path, result: dict) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
        if tomllib is not None:
            return tomllib.loads(text)
        return parse_basic_toml(text)
    except Exception as exc:  # noqa: BLE001 - report parse failure as validation data
        add(result, "errors", f"Unable to parse TOML: {exc}", path)
        return {}


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                width, height = struct.unpack(">II", header[16:24])
                return int(width), int(height)
            if header.startswith(b"\xff\xd8"):
                handle.seek(2)
                while True:
                    marker = handle.read(2)
                    if len(marker) < 2:
                        return None
                    while marker[0] != 0xFF:
                        marker = marker[1:] + handle.read(1)
                    marker_type = marker[1]
                    size_bytes = handle.read(2)
                    if len(size_bytes) < 2:
                        return None
                    size = struct.unpack(">H", size_bytes)[0]
                    if marker_type in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                        data = handle.read(5)
                        if len(data) < 5:
                            return None
                        height, width = struct.unpack(">HH", data[1:5])
                        return int(width), int(height)
                    if size < 2:
                        return None
                    handle.seek(size - 2, os.SEEK_CUR)
    except (IndexError, OSError, struct.error):
        return None
    return None


def find_preview(theme_dir: Path, stem: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = theme_dir / "images" / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def check_preview(result: dict, theme_dir: Path, stem: str, minimum: tuple[int, int]) -> None:
    path = find_preview(theme_dir, stem)
    if path is None:
        add(result, "warnings", f"Missing images/{stem}.png or images/{stem}.jpg")
        return
    size = image_size(path)
    if size is None:
        add(result, "warnings", "Unable to read image dimensions", path)
        return
    width, height = size
    if width < minimum[0] or height < minimum[1]:
        add(result, "warnings", f"{path.name} is {width}x{height}; expected at least {minimum[0]}x{minimum[1]}", path)
    if abs((width / height) - 1.5) > 0.02:
        add(result, "warnings", f"{path.name} should use a 3:2 aspect ratio; found {width}:{height}", path)
    pixel_ok, pixel_message = png_pixel_sanity(path)
    if pixel_ok is False:
        add(result, "warnings", pixel_message, path)
    elif pixel_message:
        add(result, "info" if pixel_ok else "warnings", pixel_message, path)
    add(result, "info", f"{path.name} dimensions: {width}x{height}", path)


def run_command(args: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return completed.returncode, completed.stdout.strip()


def layout_exists(layouts_dir: Path, candidates: tuple[str, ...]) -> bool:
    return any((layouts_dir / candidate).exists() for candidate in candidates)


def directory_has_files(path: Path) -> bool:
    return path.is_dir() and any(candidate.is_file() for candidate in path.rglob("*"))


def partials_state(layouts_dir: Path) -> tuple[str | None, Path | None, bool]:
    modern = layouts_dir / "_partials"
    legacy = layouts_dir / "partials"
    if directory_has_files(modern):
        return "modern", modern, True
    if directory_has_files(legacy):
        return "legacy", legacy, True
    if modern.exists():
        return "modern", modern, False
    if legacy.exists():
        return "legacy", legacy, False
    return None, None, False


def any_exists(base: Path, candidates: list[str]) -> bool:
    return any((base / candidate).exists() for candidate in candidates)


def has_hugo_config(base: Path) -> bool:
    return any((base / name).exists() for name in CONFIG_FILES + CONFIG_DIR_FILES)


def classify_root_content(path: Path, root_content: Path) -> str:
    relative = path.relative_to(root_content)
    if relative.name in ROOT_SUPPORT_CONTENT_FILES:
        return "support"
    if relative.parts and relative.parts[0] in ROOT_SUPPORT_CONTENT_DIRS:
        return "support"
    return "sample"


def png_pixel_sanity(path: Path) -> tuple[bool | None, str]:
    try:
        if path.stat().st_size > MAX_PREVIEW_IMAGE_BYTES:
            return False, f"Preview image is too large for pixel sanity check: {path.stat().st_size} bytes"
        data = path.read_bytes()
    except OSError as exc:
        return False, f"Unable to read preview image: {exc}"
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, "Pixel sanity check skipped for non-PNG preview"

    offset = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = b""
    while offset + 8 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
            bit_depth = chunk[8]
            color_type = chunk[9]
            interlace = chunk[12]
        elif kind == b"IDAT":
            compressed += chunk
        elif kind == b"IEND":
            break

    if width is None or height is None or bit_depth != 8 or color_type not in {2, 6} or interlace != 0:
        return None, "Pixel sanity check skipped for unsupported PNG format"
    if width <= 0 or height <= 0 or width * height > MAX_PREVIEW_PIXELS:
        return False, f"Preview image is too large for pixel sanity check: {width}x{height}"

    channels = 4 if color_type == 6 else 3
    stride = width * channels
    expected_raw_size = (stride + 1) * height
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, expected_raw_size + 1)
    except zlib.error as exc:
        return False, f"Unable to decompress PNG pixels: {exc}"
    if len(raw) > expected_raw_size or decompressor.unconsumed_tail:
        return False, "PNG pixel data exceeds the expected size"
    if len(raw) != expected_raw_size:
        return False, "PNG pixel data is incomplete"

    rows: list[bytes] = []
    previous = bytearray(stride)
    index = 0
    for _ in range(height):
        if index >= len(raw):
            return False, "PNG pixel data ended before all rows were decoded"
        filter_type = raw[index]
        index += 1
        row = bytearray(raw[index : index + stride])
        index += stride
        if len(row) != stride:
            return False, "PNG row data is incomplete"
        for i, value in enumerate(row):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                row[i] = (value + left) & 0xFF
            elif filter_type == 2:
                row[i] = (value + up) & 0xFF
            elif filter_type == 3:
                row[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                predictor = left + up - up_left
                pa = abs(predictor - left)
                pb = abs(predictor - up)
                pc = abs(predictor - up_left)
                row[i] = (value + (left if pa <= pb and pa <= pc else up if pb <= pc else up_left)) & 0xFF
            elif filter_type != 0:
                return None, f"Pixel sanity check skipped for unsupported PNG filter {filter_type}"
        rows.append(bytes(row))
        previous = row

    step = max(1, (width * height) // 12000)
    colors: dict[tuple[int, int, int], int] = {}
    luminance_min = 255
    luminance_max = 0
    samples = 0
    pixel_index = 0
    for row in rows:
        for column in range(0, stride, channels):
            if pixel_index % step == 0:
                color = tuple(row[column : column + 3])
                luminance = round((color[0] * 0.2126) + (color[1] * 0.7152) + (color[2] * 0.0722))
                luminance_min = min(luminance_min, luminance)
                luminance_max = max(luminance_max, luminance)
                colors[color] = colors.get(color, 0) + 1
                samples += 1
            pixel_index += 1

    if samples == 0:
        return False, "Preview image contains no sampled pixels"
    dominant_ratio = max(colors.values()) / samples
    if len(colors) <= 1:
        return False, "Preview image appears blank: all sampled pixels are identical"
    if luminance_max - luminance_min < 8:
        return False, "Preview image appears blank: sampled pixels have very low luminance variation"
    if dominant_ratio > 0.995:
        return False, "Preview image appears to be mostly a single background color"
    return True, f"Pixel sanity check passed: {len(colors)} sampled colors, luminance range {luminance_min}-{luminance_max}"


def example_site_config(example_site: Path, result: dict) -> dict:
    for name in CONFIG_FILES + CONFIG_DIR_FILES:
        path = example_site / name
        if path.exists() and path.suffix == ".toml":
            return read_toml(path, result)
    return {}


def check_multilingual_links(result: dict, example_site: Path) -> None:
    config = example_site_config(example_site, result)
    languages = config.get("languages", {}) if isinstance(config, dict) else {}
    if not isinstance(languages, dict) or len(languages) < 2 or not config.get("defaultContentLanguageInSubdir"):
        return
    language_codes = set(languages.keys())
    content_dir = example_site / "content"
    if not content_dir.exists():
        return
    for markdown in content_dir.rglob("*.md"):
        try:
            relative = markdown.relative_to(content_dir)
        except ValueError:
            continue
        if not relative.parts or relative.parts[0] not in language_codes:
            continue
        language = relative.parts[0]
        try:
            text = markdown.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target.startswith("/") or target.startswith("//"):
                continue
            path = target.split("#", 1)[0].split("?", 1)[0]
            if not path or Path(path).suffix.lower() in CONTENT_ASSET_SUFFIXES:
                continue
            if not (path == f"/{language}" or path.startswith(f"/{language}/")):
                add(
                    result,
                    "warnings",
                    f"Multilingual exampleSite link should stay in the '{language}' branch: {target}",
                    markdown,
                )


def check_hardcoded_replaceable_images(result: dict, theme_dir: Path) -> None:
    checked_roots = [theme_dir / "layouts", theme_dir / "assets"]
    warnings = 0
    for root in checked_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_FILE_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                continue
            for match in HARDCODED_IMAGE_PATH_RE.finditer(text):
                image_path = match.group(1)
                image_name = Path(image_path).name.lower()
                if not any(hint in image_name for hint in REPLACEABLE_IMAGE_HINTS):
                    continue
                add(
                    result,
                    "warnings",
                    f"Publication check: hardcoded replaceable image path '{image_path}'. Prefer params, front matter, page resources, or data files with a fallback default.",
                    path,
                )
                warnings += 1
                if warnings >= 8:
                    add(result, "info", "Skipped additional hardcoded replaceable image warnings after first 8 matches")
                    return


def read_text_if_possible(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def collect_text_from_roots(roots: list[Path]) -> dict[Path, str]:
    texts: dict[Path, str] = {}
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in TEXT_FILE_SUFFIXES or root.name in README_FILES:
                text = read_text_if_possible(root)
                if text:
                    texts[root] = text
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_FILE_SUFFIXES and path.name not in README_FILES:
                continue
            text = read_text_if_possible(path)
            if text:
                texts[path] = text
    return texts


def check_footer_theme_attribution(result: dict, theme_dir: Path) -> None:
    roots = [
        theme_dir / "layouts",
        theme_dir / "i18n",
        theme_dir / "README.md",
        theme_dir / "README.markdown",
        theme_dir / "README",
        theme_dir / "hugo.toml",
        theme_dir / "config.toml",
        theme_dir / "config",
        theme_dir / "exampleSite" / "hugo.toml",
        theme_dir / "exampleSite" / "config.toml",
        theme_dir / "exampleSite" / "config",
    ]
    texts = collect_text_from_roots(roots)
    implementation_text = "\n".join(text for path, text in texts.items() if path.name not in README_FILES)

    missing_keys = [key for key in FOOTER_ATTRIBUTION_KEYS if key not in implementation_text]
    if missing_keys:
        add(
            result,
            "warnings",
            "Publication check: missing footer theme attribution params: " + ", ".join(missing_keys),
        )

    readme_text = "\n".join(text for path, text in texts.items() if path.name in README_FILES)
    missing_readme_keys = [key for key in FOOTER_ATTRIBUTION_KEYS if key not in readme_text]
    if missing_readme_keys:
        add(
            result,
            "warnings",
            "Publication check: README should document footer theme attribution params: " + ", ".join(missing_readme_keys),
        )

    i18n_text = "\n".join(text for path, text in texts.items() if "i18n" in path.parts)
    layout_text = "\n".join(text for path, text in texts.items() if "layouts" in path.parts)
    if not any(hint in i18n_text for hint in FOOTER_ATTRIBUTION_I18N_HINTS):
        add(result, "warnings", "Publication check: footer theme attribution sentence should be localizable through i18n")
    if "showThemeAttribution" not in layout_text:
        add(result, "warnings", "Publication check: layouts should render footer theme attribution behind params.footer.showThemeAttribution")


def detect_build_command(theme_dir: Path, site_dir: Path | None) -> tuple[Path, list[str]] | None:
    theme_name = theme_dir.name
    if site_dir is not None:
        if (site_dir / "themes" / theme_name).exists():
            return site_dir, ["hugo", "--theme", theme_name]
        return site_dir, ["hugo", "--themesDir", str(theme_dir.parent), "--theme", theme_name]
    example_site = theme_dir / "exampleSite"
    if example_site.exists():
        return example_site, ["hugo", "--themesDir", str(theme_dir.parent), "--theme", theme_name]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-dir", required=True, type=Path, help="Path to the Hugo theme directory")
    parser.add_argument("--site-dir", type=Path, help="Optional Hugo site directory for smoke build")
    parser.add_argument("--mode", choices=("new", "port"), default="new", help="Validation profile: new generated theme variant or known-theme port")
    parser.add_argument("--skip-build", action="store_true", help="Skip the Hugo smoke build")
    parser.add_argument("--publication", action="store_true", help="Run additional GitHub/themes.gohugo.io package checks")
    parser.add_argument("--timeout", type=int, default=60, help="Hugo command timeout in seconds")
    args = parser.parse_args()

    theme_dir = args.theme_dir.resolve()
    site_dir = args.site_dir.resolve() if args.site_dir else None
    result = {"ok": True, "theme_dir": str(theme_dir), "errors": [], "warnings": [], "info": []}

    hugo = shutil.which("hugo")
    if hugo is None:
        add(result, "errors", "hugo executable not found on PATH")
    else:
        code, output = run_command([hugo, "version"], theme_dir if theme_dir.exists() else Path.cwd(), args.timeout)
        if code == 0:
            add(result, "info", output.splitlines()[0] if output else "hugo version command succeeded")
        else:
            add(result, "errors", f"hugo version failed: {output}")

    if not theme_dir.exists() or not theme_dir.is_dir():
        add(result, "errors", "Theme directory does not exist", theme_dir)
    else:
        required_dirs = PORT_REQUIRED_DIRS if args.mode == "port" else REQUIRED_DIRS
        for directory in required_dirs:
            path = theme_dir / directory
            if not path.exists():
                add(result, "warnings", f"Missing generated skeleton directory: {directory}/", path)

        layouts_dir = theme_dir / "layouts"
        if not layout_exists(layouts_dir, ("baseof.html", "_default/baseof.html", "home.html", "index.html")):
            add(result, "warnings", "No base or home/index layout found under layouts/", layouts_dir)
        partials_kind, partials_path, partials_has_files = partials_state(layouts_dir)
        if partials_path is None:
            add(result, "warnings", "No partials directory found under layouts/; expected _partials/ for modern Hugo or partials/ for legacy themes", layouts_dir)
        elif not partials_has_files:
            add(result, "warnings", f"Partials directory is empty: layouts/{partials_path.name}", partials_path)
        elif partials_kind == "modern":
            add(result, "info", "Modern Hugo partials directory detected: layouts/_partials", partials_path)
        elif partials_kind == "legacy":
            add(result, "info", "Legacy Hugo partials directory detected: layouts/partials", partials_path)

        theme_toml = theme_dir / "theme.toml"
        if not theme_toml.exists():
            add(result, "warnings", "Missing theme.toml; required for themes.gohugo.io submissions", theme_toml)
        else:
            metadata = read_toml(theme_toml, result)
            for key in THEMES_SITE_REQUIRED_META:
                if not metadata.get(key):
                    add(result, "warnings", f"theme.toml missing recommended field: {key}", theme_toml)
            module = metadata.get("module", {}) if isinstance(metadata, dict) else {}
            hugo_version = module.get("hugoVersion", {}) if isinstance(module, dict) else {}
            if not hugo_version and not metadata.get("min_version"):
                add(result, "warnings", "No Hugo compatibility metadata found in theme.toml", theme_toml)
            if args.mode == "port" and not metadata.get("original"):
                add(result, "warnings", "Port mode: theme.toml should include [original] metadata for known-theme ports", theme_toml)

        if not has_hugo_config(theme_dir):
            add(result, "warnings", "No root Hugo config file found in theme directory")

        if args.publication:
            for artifact in BUILD_ARTIFACTS:
                artifact_path = theme_dir / artifact
                if artifact_path.exists():
                    add(result, "warnings", f"Build artifact should not be committed in theme root: {artifact}", artifact_path)
            if not any_exists(theme_dir, README_FILES):
                add(result, "warnings", "Publication check: missing README.md")
            if not any_exists(theme_dir, LICENSE_FILES):
                add(result, "warnings", "Publication check: missing LICENSE file")
            if not layout_exists(layouts_dir, ("404.html", "_default/404.html")):
                add(result, "warnings", "Publication check: missing 404 layout", layouts_dir)
            if not layout_exists(layouts_dir, ("_default/rss.xml", "rss.xml")):
                add(result, "warnings", "Publication check: missing RSS layout", layouts_dir)
            if not any_exists(theme_dir, FAVICON_CANDIDATES):
                add(result, "warnings", "Publication check: no favicon or webmanifest asset detected")
            check_hardcoded_replaceable_images(result, theme_dir)
            check_footer_theme_attribution(result, theme_dir)

        root_content = theme_dir / "content"
        if root_content.exists():
            root_markdown = list(root_content.rglob("*.md"))
            if root_markdown:
                sample_markdown = [path for path in root_markdown if classify_root_content(path, root_content) == "sample"]
                if sample_markdown:
                    add(
                        result,
                        "warnings",
                        f"Theme root content contains {len(sample_markdown)} sample Markdown file(s); for new variants, keep demo content in exampleSite/content to avoid sample-content leakage",
                        root_content,
                    )
                else:
                    add(result, "info", f"Theme root content contains {len(root_markdown)} support Markdown file(s)", root_content)

        example_site = theme_dir / "exampleSite"
        if not example_site.exists():
            if args.mode == "new":
                add(result, "warnings", "Missing exampleSite/; new theme variants should include a design-matching demo site", example_site)
            else:
                add(result, "info", "No exampleSite found; acceptable for port mode when package docs provide build/demo guidance", example_site)
        else:
            for artifact in BUILD_ARTIFACTS:
                artifact_path = example_site / artifact
                if artifact_path.exists():
                    add(result, "warnings", f"Build artifact should not be committed in exampleSite: {artifact}", artifact_path)
            if not has_hugo_config(example_site):
                add(result, "warnings", "exampleSite is missing a Hugo config file", example_site)
            if not (example_site / "content").exists():
                add(result, "warnings", "exampleSite is missing content/", example_site / "content")
            else:
                markdown_files = list((example_site / "content").rglob("*.md"))
                if not markdown_files:
                    add(result, "warnings", "exampleSite/content contains no Markdown sample content", example_site / "content")
                else:
                    add(result, "info", f"exampleSite content files: {len(markdown_files)}", example_site / "content")
            check_multilingual_links(result, example_site)

        check_preview(result, theme_dir, "screenshot", (1500, 1000))
        check_preview(result, theme_dir, "tn", (900, 600))

        if not args.skip_build and hugo is not None:
            build = detect_build_command(theme_dir, site_dir)
            if build is None:
                add(result, "warnings", "No site-dir or exampleSite found; skipped Hugo smoke build")
            else:
                cwd, command = build
                with tempfile.TemporaryDirectory(prefix="hugo-theme-check-") as destination:
                    build_command = command + ["--destination", destination, "--noBuildLock"]
                    code, output = run_command(build_command, cwd, args.timeout)
                if code == 0:
                    add(result, "info", "Hugo smoke build succeeded", cwd)
                else:
                    add(result, "errors", f"Hugo smoke build failed with exit code {code}: {output}", cwd)

    result["ok"] = not result["errors"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
