#!/usr/bin/env python3
"""Capture Hugo theme preview images from a running local site."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
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
        f"--screenshot={output}",
        f"--window-size={width},{height}",
        url,
    ]


def run_capture(command: list[str], timeout: int) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
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

    browser = detect_browser(args.browser)
    if browser is None:
        add(result, "errors", "No supported headless browser found. Install Firefox, Chrome, or Chromium, or pass --browser explicitly.")
        result["ok"] = False
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    browser_name, executable = browser
    images_dir = theme_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    add(result, "info", f"Using {browser_name}: {executable}")

    targets = [
        ("screenshot.png", args.screenshot_size),
        ("tn.png", args.thumbnail_size),
    ]
    for filename, size in targets:
        output = images_dir / filename
        ok, output_text = capture(browser_name, executable, args.url, output, size, args.timeout)
        if ok:
            result["files"].append(str(output))
            add(result, "info", f"Captured {filename} at {size[0]}x{size[1]}", output)
        else:
            detail = f": {output_text}" if output_text else ""
            add(result, "errors", f"Failed to capture {filename}{detail}", output)

    result["ok"] = not result["errors"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
