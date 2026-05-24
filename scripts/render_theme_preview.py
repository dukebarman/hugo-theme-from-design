#!/usr/bin/env python3
"""Capture Hugo theme preview images from a running local site."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path


BROWSERS = {
    "firefox": [
        "firefox",
        "/Applications/Firefox.app/Contents/MacOS/firefox",
    ],
    "chrome": [
        "google-chrome",
        "chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "chromium": [
        "chromium",
        "chromium-browser",
    ],
}


class PreviewURLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_refresh: str | None = None
        self.canonical: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs if value is not None}
        if tag.lower() == "meta" and values.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"(?:^|;)\s*url\s*=\s*([^;]+)", values.get("content", ""), re.IGNORECASE)
            if match:
                self.meta_refresh = match.group(1).strip(" '\"")
        if tag.lower() == "link" and "canonical" in values.get("rel", "").lower().split():
            self.canonical = values.get("href")


def add(result: dict, level: str, message: str, path: Path | None = None) -> None:
    entry = {"message": message}
    if path is not None:
        entry["path"] = str(path)
    result[level].append(entry)


def parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", 1)
        parsed = int(width), int(height)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Size must use WIDTHxHEIGHT, for example 1500x1000") from exc
    if parsed[0] <= 0 or parsed[1] <= 0:
        raise argparse.ArgumentTypeError("Size dimensions must be positive")
    return parsed


def resolve_executable(candidate: str) -> Path | None:
    path = Path(candidate)
    if path.is_absolute() and path.exists():
        return path
    resolved = shutil.which(candidate)
    if resolved:
        return Path(resolved)
    return None


def detect_browser(preference: str) -> tuple[str, Path] | None:
    names = list(BROWSERS) if preference == "auto" else [preference]
    for name in names:
        for candidate in BROWSERS[name]:
            executable = resolve_executable(candidate)
            if executable is not None:
                return name, executable
    return None


def same_origin(left: str, right: str) -> bool:
    left_url = urllib.parse.urlparse(left)
    right_url = urllib.parse.urlparse(right)
    return (left_url.scheme, left_url.netloc) == (right_url.scheme, right_url.netloc)


def resolve_preview_url(url: str, timeout: int) -> tuple[str, list[str], list[str]]:
    info: list[str] = []
    warnings: list[str] = []
    request = urllib.request.Request(url, headers={"User-Agent": "hugo-theme-preview/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            resolved_url = response.geturl()
            content_type = response.headers.get("content-type", "")
            body = response.read(262144)
    except (OSError, urllib.error.URLError) as exc:
        warnings.append(f"Unable to preflight preview URL; using original URL: {exc}")
        return url, info, warnings

    if resolved_url != url:
        info.append(f"HTTP redirect resolved preview URL to {resolved_url}")
    if "html" not in content_type.lower():
        return resolved_url, info, warnings

    parser = PreviewURLParser()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 - keep preview capture resilient
        warnings.append(f"Unable to parse preview HTML for redirects: {exc}")
        return resolved_url, info, warnings

    if parser.meta_refresh:
        target = urllib.parse.urljoin(resolved_url, parser.meta_refresh)
        if same_origin(resolved_url, target):
            info.append(f"Meta refresh resolved preview URL to {target}")
            return target, info, warnings
        warnings.append(f"Ignoring cross-origin meta refresh preview URL: {target}")
    if parser.canonical:
        target = urllib.parse.urljoin(resolved_url, parser.canonical)
        source_path = urllib.parse.urlparse(resolved_url).path or "/"
        if target != resolved_url and same_origin(resolved_url, target) and source_path in {"", "/"}:
            info.append(f"Canonical URL resolved root preview URL to {target}")
            return target, info, warnings
        if target != resolved_url:
            warnings.append(f"Canonical URL differs from preview URL: {target}")
    return resolved_url, info, warnings


def browser_command(browser: str, executable: Path, url: str, output: Path, size: tuple[int, int], profile: Path | None) -> list[str]:
    width, height = size
    if browser == "firefox":
        command = [
            str(executable),
            "--headless",
            "--screenshot",
            str(output),
            "--window-size",
            f"{width},{height}",
        ]
        if profile is not None:
            command.extend(["--profile", str(profile)])
        command.append(url)
        return command
    return [
        str(executable),
        "--headless=new",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=3000",
        f"--screenshot={output}",
        f"--window-size={width},{height}",
        url,
    ]


def run_capture(command: list[str], timeout: int) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or exc.stderr or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        detail = output.strip()
        message = f"Browser command timed out after {timeout}s"
        return 124, f"{message}: {detail}" if detail else message
    except OSError as exc:
        return 127, f"Unable to run browser command: {exc}"
    return completed.returncode, completed.stdout.strip()


def capture(browser: str, executable: Path, url: str, output: Path, size: tuple[int, int], timeout: int) -> tuple[bool, str]:
    if browser == "firefox":
        with tempfile.TemporaryDirectory(prefix="hugo-theme-preview-firefox-") as profile:
            command = browser_command(browser, executable, url, output, size, Path(profile))
            code, output_text = run_capture(command, timeout)
    else:
        command = browser_command(browser, executable, url, output, size, None)
        code, output_text = run_capture(command, timeout)
    return code == 0 and output.exists(), output_text


def png_pixel_sanity(path: Path) -> tuple[bool | None, str]:
    try:
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

    channels = 4 if color_type == 6 else 3
    stride = width * channels
    try:
        raw = zlib.decompress(compressed)
    except zlib.error as exc:
        return False, f"Unable to decompress PNG pixels: {exc}"

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Rendered local site URL, for example http://127.0.0.1:1313/")
    parser.add_argument("--theme-dir", required=True, type=Path, help="Path to the Hugo theme directory")
    parser.add_argument("--browser", choices=("auto", "firefox", "chrome", "chromium"), default="auto")
    parser.add_argument("--screenshot-size", type=parse_size, default=(1500, 1000), help="Full screenshot size, default 1500x1000")
    parser.add_argument("--thumbnail-size", type=parse_size, default=(900, 600), help="Thumbnail size, default 900x600")
    parser.add_argument("--timeout", type=int, default=30, help="Browser command timeout in seconds")
    args = parser.parse_args()

    theme_dir = args.theme_dir.resolve()
    result = {"ok": True, "theme_dir": str(theme_dir), "errors": [], "warnings": [], "info": [], "files": []}

    if not theme_dir.exists() or not theme_dir.is_dir():
        add(result, "errors", "Theme directory does not exist", theme_dir)
        result["ok"] = False
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    browser = detect_browser(args.browser)
    if browser is None:
        add(result, "errors", "No supported headless browser found. Install Firefox, Chrome, or Chromium, or pass --browser explicitly.")
        result["ok"] = False
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    browser_name, executable = browser
    images_dir = theme_dir / "images"
    try:
        images_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        add(result, "errors", f"Unable to create images directory: {exc}", images_dir)
        result["ok"] = False
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    add(result, "info", f"Using {browser_name}: {executable}")

    preview_url, url_info, url_warnings = resolve_preview_url(args.url, args.timeout)
    for message in url_info:
        add(result, "info", message)
    for message in url_warnings:
        add(result, "warnings", message)

    targets = [
        ("screenshot.png", args.screenshot_size),
        ("tn.png", args.thumbnail_size),
    ]
    for filename, size in targets:
        output = images_dir / filename
        ok, output_text = capture(browser_name, executable, preview_url, output, size, args.timeout)
        if ok:
            pixel_ok, pixel_message = png_pixel_sanity(output)
            if pixel_ok is False:
                add(result, "errors", pixel_message, output)
            else:
                result["files"].append(str(output))
                add(result, "info", f"Captured {filename} at {size[0]}x{size[1]}", output)
                add(result, "info" if pixel_ok else "warnings", pixel_message, output)
        else:
            detail = f": {output_text}" if output_text else ""
            add(result, "errors", f"Failed to capture {filename}{detail}", output)

    result["ok"] = not result["errors"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
