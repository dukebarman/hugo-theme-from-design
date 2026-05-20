#!/usr/bin/env python3
"""Structural and smoke-build checks for Hugo themes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


REQUIRED_DIRS = ["archetypes", "assets", "content", "data", "i18n", "layouts", "static"]
PORT_REQUIRED_DIRS = ["archetypes", "assets", "layouts", "static"]
THEMES_SITE_REQUIRED_META = ["name", "license", "licenselink", "description", "homepage"]
BUILD_ARTIFACTS = ["public", ".hugo_build.lock", "resources"]
CONFIG_FILES = ("hugo.toml", "config.toml", "config.yaml", "config.json")
CONFIG_DIR_FILES = (
    "config/_default/hugo.toml",
    "config/_default/config.toml",
    "config/_default/config.yaml",
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


def add(result: dict, level: str, message: str, path: Path | None = None) -> None:
    entry = {"message": message}
    if path is not None:
        entry["path"] = str(path)
    result[level].append(entry)


def read_toml(path: Path, result: dict) -> dict:
    if tomllib is None:
        add(result, "warnings", "Python tomllib is unavailable; skipping TOML parsing", path)
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
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
                    handle.seek(size - 2, os.SEEK_CUR)
    except OSError:
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
        if not layout_exists(layouts_dir, ("_partials", "partials")):
            add(result, "warnings", "No partials directory found under layouts/; expected _partials/ for modern Hugo or partials/ for legacy themes", layouts_dir)
        elif (layouts_dir / "_partials").exists():
            add(result, "info", "Modern Hugo partials directory detected: layouts/_partials", layouts_dir / "_partials")
        elif (layouts_dir / "partials").exists():
            add(result, "info", "Legacy Hugo partials directory detected: layouts/partials", layouts_dir / "partials")

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
