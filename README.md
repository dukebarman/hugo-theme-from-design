# Hugo Theme From Design

Codex skill for creating, updating, and repairing Hugo themes from design references such as Figma frames, exported assets, screenshots, or existing Hugo theme repositories.

The skill is aimed at turning a visual design into a reusable Hugo theme package, not just a static screenshot match. It guides Codex through theme scaffolding, `exampleSite` generation, Hugo build validation, preview image capture, and package-readiness checks for public theme repositories, including configurable footer attribution.

For publishable blog, magazine, documentation, and long-form article themes, the skill can also prepare renderer-friendly article markup for Telegram Instant View and similar extractors. This is optional: the generated theme can expose stable selectors and a sample IV template, but Telegram Instant View must still be configured and validated per live domain in Telegram's editor.

## When to use it

Use `$hugo-theme-from-design` when you want Codex to:

- create a new Hugo theme variant from a Figma frame, PNG, or JPG reference;
- match an existing Hugo theme to a visual design;
- repair Hugo layout, asset, metadata, or build issues;
- migrate or modernize an older Hugo theme while preserving its public surface;
- prepare a theme for GitHub or `themes.gohugo.io` publication.

## What it includes

- `SKILL.md` - the main workflow and implementation rules for Codex.
- `assets/telegram-instant-view.tpl` - reusable starting template for optional Telegram Instant View support in article-focused themes.
- `references/` - Hugo packaging notes, UI review guidance, and theme tutorial findings.
- `scripts/hugo_theme_check.py` - structural checks, metadata checks, and optional Hugo smoke builds.
- `scripts/render_theme_preview.py` - headless browser capture for `images/screenshot.png` and `images/tn.png`.
- `tests/` - unit tests for the helper scripts.
- `agents/openai.yaml` - display metadata for OpenAI/Codex skill interfaces.

## Requirements

- Codex with local skills support.
- Hugo available on `PATH` for build validation.
- Python 3.10 or newer for the helper scripts.
- Firefox, Chrome, or Chromium for automated preview image capture.

The skill can still guide implementation without every optional tool installed, but final validation is strongest when Hugo and a headless browser are available.

## Installation

Clone or copy this directory into your Codex skills directory. If `CODEX_HOME`
is not set, use `~/.codex`. Do not run `mkdir -p "$CODEX_HOME/skills"` with an
empty `CODEX_HOME`: it expands to `/skills`, which is read-only on many macOS
systems.

```bash
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"
git clone https://github.com/dukebarman/hugo-theme-from-design.git "$SKILLS_DIR/hugo-theme-from-design"
```

If your agent runner loads skills from Agents-style directories, install it
there instead:

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/dukebarman/hugo-theme-from-design.git "$HOME/.agents/skills/hugo-theme-from-design"
```

For a project-local install, clone it under the project:

```bash
cd /path/to/your-hugo-project
mkdir -p .agents/skills
git clone https://github.com/dukebarman/hugo-theme-from-design.git .agents/skills/hugo-theme-from-design
```

Then invoke it in Codex with:

```text
Use $hugo-theme-from-design to create a Hugo theme from this screenshot.
```

## Typical workflow

1. Provide Codex with a design reference, such as a screenshot, Figma export, or existing theme repository.
2. Ask for a new variant, a compatible port, an update, or a repair.
3. Codex inspects the Hugo project, scaffolds or updates the theme, and creates an `exampleSite` when appropriate.
4. Codex validates the result with Hugo and the bundled checker.
5. For publishable themes, Codex can capture preview images and run additional package-readiness checks.

## Helper commands

Run the structural checker against a theme:

```bash
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme
```

Run publication-oriented checks:

```bash
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --publication
```

When a theme declares Telegram Instant View support in its README or includes
`docs/telegram-instant-view.tpl`, publication checks emit warning-level
guidance for stable article selectors, article metadata, image metadata, README
documentation, and per-domain Telegram template wording. These checks are not
errors and are not applied to themes that do not declare IV support.

Validate a known-theme port:

```bash
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --mode port --publication
```

Capture preview images from a running local Hugo server:

```bash
python3 scripts/render_theme_preview.py \
  --url http://127.0.0.1:1313/ \
  --theme-dir /path/to/theme
```

Run the unit tests:

```bash
python3 -m unittest discover -s tests
```

## Development notes

Keep `SKILL.md` focused on instructions Codex should follow during task execution. Put longer background material, checklists, and research notes in `references/` so the skill can load them only when relevant.

When updating helper scripts, add or update focused tests under `tests/` and run the full unittest suite before publishing changes.

## Telegram Instant View

The skill treats Telegram Instant View as an optional publication pattern for
article-focused Hugo themes. When requested, Codex should add stable selectors
such as `article[data-iv-article]`, `.iv-title`, `[data-iv-published]`,
`[data-iv-content]`, optional `[data-iv-cover]`, and `[data-iv-remove]` for UI
chrome that should not appear in the rendered article.

The theme should also provide article metadata such as canonical URL,
description, Open Graph article fields, `og:image`,
`article:published_time`, `article:modified_time`, and `article:author`, plus
front matter conventions for cover images and authors. Markdown image and code
render hooks should preserve figure captions and code language metadata when
the theme needs publication-grade article rendering.

`assets/telegram-instant-view.tpl` is a reusable starting point for a theme-level
`docs/telegram-instant-view.tpl`. Adapt its `?path` rule to the live site URL
structure, such as `/posts/`, `/blog/`, `/articles/`, or `/docs/`. The theme
does not enable Telegram Instant View automatically; site owners must configure
and validate the template for their live domain in Telegram's editor. Official
documentation: https://instantview.telegram.org/docs/

## License

Apache-2.0. See [LICENSE](LICENSE).
