---
name: hugo-theme-from-design
description: Create, update, and repair Hugo themes from Figma frames, exported design assets, PNG/JPG screenshots, or existing Hugo theme repositories. Use when Codex needs to turn a website design into a Hugo theme, match a Hugo theme to a visual reference, fix Hugo layout/assets issues, scaffold with `hugo new theme`, validate theme metadata, or improve theme UX/UI against a design brief.
---

# Hugo Theme From Design

## Workflow

Default to generating a new theme variant from the design reference. Update or migrate an existing/old theme only when the user explicitly asks, when the task is framed as a repair, or when the repository clearly has a single theme that must be preserved.

1. Establish the target: new variant, port/reimplementation of a known theme, update to an existing theme, migration from an old theme, or repair. Identify the design source (Figma, PNG/JPG screenshot, design tokens, existing site) and the expected Hugo version/content model. If an original/comparison theme is supplied and the user has not made the goal clear, ask one concise clarification: whether to create a visually inspired new variant or a compatible port preserving the original theme's public API.
2. Inspect the repository before editing: `hugo version`, `find . -maxdepth 3`, theme `layouts/`, `assets/`, `static/`, `content/`, `data/`, `i18n/`, config files, `theme.toml`, and any `exampleSite`. Detect whether the theme uses the modern Hugo template layout (`layouts/_partials`, root `baseof.html`, `home.html`, `page.html`, `section.html`) or legacy-compatible layout (`layouts/partials`, `layouts/_default/*`).
3. If creating the default new variant, prefer `hugo new theme <variant-name>` when Hugo is installed. Run it from the intended site/repository root or pass paths deliberately, then verify the created directory is exactly the target theme path before editing. Preserve Hugo's generated skeleton and build on top of it instead of inventing a custom structure.
4. Separate the actual website UI from presentation context. If a PNG/JPG shows a browser window, device mockup, gradient poster background, drop shadow, or gallery frame around the site, treat those as preview/presentation chrome unless the user explicitly asks to make them part of the live theme.
5. Translate the design into Hugo boundaries:
   - templates in `layouts/`, with a base template, page/list or page/section/home templates, and reusable partials;
   - CSS/Sass/JS/images in `assets/` when they should go through Hugo Pipes, or `static/` when copied as-is;
   - design-matching demo content and config in `exampleSite/`;
   - theme parameters in config instead of hard-coded copy when users should customize them;
   - homepage selection rules, such as `featured = true`, when the design shows a specific post or project instead of a generic latest-item feed.
6. Generate `exampleSite` for new variants by default. Its pages, sections, menus, params, sample images, and front matter should demonstrate the received design, not generic placeholder content. Move or remove the sample Markdown created by `hugo new theme` in the theme root `content/`; root `content/` can stay as an empty skeleton directory, but demo pages belong in `exampleSite/content/`.
7. Implement visually first, then wire content behavior. Match spacing, hierarchy, color, typography, breakpoints, navigation, cards, media treatment, and states from the actual site UI in the design reference before adding optional features.
8. Validate with `scripts/hugo_theme_check.py` and a real Hugo build/server. Fix template errors, broken assets, missing metadata, responsive regressions, and obvious UX issues before finishing.

## Design Intake

For Figma sources, use available Figma exports or MCP/API data when the environment provides them. Extract frame dimensions, spacing, colors, typography, component variants, image assets, and interaction states. If direct Figma access is unavailable, ask for exported PNG/JPG plus any fonts/assets that are not already in the repo.

For PNG/JPG-only sources, infer layout deliberately:
- measure the viewport and major regions before coding;
- identify repeated components and convert them to partials;
- preserve information hierarchy over pixel-perfect trivia;
- avoid using a screenshot as the UI background except for explicit mockups;
- identify whether gradients, browser chrome, device bezels, rounded outer cards, shadows, and wallpaper are part of the actual website or only a presentation wrapper.

When the design is a screenshot of a site inside a browser/device frame, implement the site inside the frame, not the frame itself. Use the presentation wrapper only for `images/screenshot.*`, marketing previews, or docs unless the user explicitly asks for an in-page browser mockup.

When a reference shows light and dark appearances simultaneously, treat it as a color-mode specification by default, not as a permanent split-screen layout. Implement one coherent theme with light and dark token sets, a visible toggle when the reference shows one, and sensible initialization from stored preference or `prefers-color-scheme`. Preserve the simultaneous light/dark composition only for preview images or when the user explicitly asks for a split-mode page.

When updating an existing theme, keep its public configuration and content conventions stable unless the user asks for a breaking redesign.

## New Variant Vs Update

For a new design request, create a new variant rather than overwriting the old theme. Choose a clear variant name from the design direction or user-provided name, scaffold or copy only the minimum reusable pieces needed, and keep the original theme intact for comparison and rollback.

If the design is clearly a known theme or port target, such as Hyde, Poole, PaperMod, Blonde, or another named theme, treat it as a port/reimplementation task rather than a pure new-variant task. Preserve the recognizable architecture and public configuration where it matters: original metadata in `theme.toml`, README/license attribution, established CSS/module split, theme params, 404/RSS/code/print styles, and compatibility conventions. Do not force `exampleSite` if the target package style intentionally omits it, but provide a buildable demo site when the user asks for a generated variant.

Before reimplementing or comparing against an existing theme, audit its compatibility surface:
- config params and menus from `hugo.toml`, `config/_default/*`, README examples, and `exampleSite`;
- widgets, partial extension points, shortcodes, render hooks, taxonomies, content section names, and archetypes;
- asset/icon strategy and whether an npm/Tailwind/PostCSS/Sass pipeline is part of the public development workflow;
- optional integrations such as search, Pagefind, analytics, comments, ads, social/share links, PWA, or multilingual support.

Then choose and state one of two paths: preserve that surface for a compatible port, or intentionally produce a simpler new variant and call out the features not carried over. If the user has already said "new theme", "new variant", "test the skill", or provided only a screenshot, default to the simpler new-variant path without stopping for clarification.

For an update/migration from an old theme:
- audit current layouts, params, content types, menus, taxonomies, shortcodes, i18n, assets, and public configuration before editing;
- preserve existing URLs, front matter contracts, params, and documented customization points unless the user approves a breaking change;
- migrate template conventions only when needed for the requested update or current Hugo compatibility;
- update or add `exampleSite` so it demonstrates the migrated design and catches compatibility regressions;
- keep old-to-new mapping notes in the final answer so users know what changed.

## ExampleSite Generation

For every new theme variant, create `exampleSite/` inside the theme. Model the structure after mature Hugo themes or any local examples present in the workspace, but tailor content to the received design.

The minimum useful `exampleSite` includes:
- `exampleSite/hugo.toml` with `baseURL`, `languageCode`, `title`, `theme = "<theme-folder-name>"`, menus, taxonomies, and `[params]` values needed by the design;
- `exampleSite/content/_index.md` for homepage content/front matter;
- section content matching the design, such as `posts/`, `portfolio/`, `about/`, `services/`, `projects/`, `docs/`, or `contact/`;
- enough sample Markdown to exercise home, section/list, page/single, taxonomy/term, pagination, media cards, navigation, footer, and empty/long text states;
- sample front matter for design-specific fields such as hero images, eyebrow text, CTAs, featured flags, authors, tags, dates, summaries, external links, and gallery assets.

Keep generated demo content credible but lightweight. Do not put built output such as `public/` or `.hugo_build.lock` into the theme unless the user explicitly wants generated artifacts.

## Production Readiness

For quick design tests, keep the theme focused and small. For a publishable GitHub theme or a theme intended for `themes.gohugo.io`, read the production checklist in `references/hugo-theme-notes.md` and add the expected package surface: README, license, richer `exampleSite`, favicon/webmanifest assets, 404/RSS/templates, responsive mobile navigation, code styles when posts include code, and documented params.

Do not confuse a visually plausible prototype with a reusable theme product. When the user compares against a mature human-made theme or plans to publish the result, graduate the implementation beyond screenshot matching:
- replace decorative or placeholder UI with working Hugo behavior, or remove controls that are only visual;
- implement pagination with Hugo pagination APIs when lists can exceed one page;
- use real icon assets or an icon partial instead of unicode stand-ins for reusable theme UI;
- make post images robust with page resources/static assets and resizing where practical;
- add search, comments, PWA, i18n, analytics, or shortcodes only when requested or implied, but make advertised features actually work;
- generate preview screenshots from the rendered theme when a browser screenshot tool is available instead of drawing schematic placeholder previews.

## Hugo Implementation Rules

Read `references/hugo-theme-notes.md` when the task involves scaffolding, theme-store readiness, metadata, or unfamiliar Hugo structure.
Read `references/hugo-theme-guide-findings.md` when validating the workflow against common third-party tutorials or when the user asks for a tutorial-style theme implementation.

Prefer the repo's current Hugo style:
- Go templates and partial naming already present in the theme;
- Hugo Pipes patterns already used in `assets/`;
- config style already present, including `hugo.toml`, `config.toml`, or `config/_default/*.toml`;
- existing parameter names, menu conventions, taxonomy structure, and i18n keys;
- minimal dependencies unless the theme already uses npm/Vite/PostCSS/Sass.

For Hugo `v0.146+`, prefer the modern template layout for new work unless the repository clearly uses legacy conventions. For existing themes, do not migrate `_default` to root templates or `partials` to `_partials` as an incidental change; only migrate when the user asks or Hugo build errors require it.

Ensure child templates define the same blocks used by the base template, typically `{{ define "main" }}`. When calling partials that need page/site data, pass context explicitly with `.` or a focused `dict`.

If config params allow Markdown for visible text, render visible text with `markdownify` but sanitize metadata attributes with `markdownify | plainify` before placing them in `<meta>` tags, `title`, `aria-label`, or other plain-text attributes.

If JavaScript wires visible controls such as color-mode toggles, mobile menus, language buttons, search, or filters, ensure the code runs after the relevant DOM exists. Prefer `defer` in the script tag or bind events on `DOMContentLoaded` when scripts are emitted in `<head>`. Verify that the control works in a browser, not only that Hugo builds.

Do not delete user layouts, params, content, translations, or generated visual assets just because they are outside the current design. Work around them or preserve compatibility.

Use these commands as the baseline:

```bash
hugo version
hugo new theme <theme-name>
hugo --source <site-or-exampleSite> --theme <theme-name> --destination /tmp/<theme-name>-public --noBuildLock
hugo server --source <site-or-exampleSite> --theme <theme-name> --disableFastRender --renderToMemory --noBuildLock
```

For standalone theme repositories, build the included `exampleSite` when present. For new variants, create `exampleSite` before final validation. For old themes without `exampleSite`, either add one as part of the migration/update or clearly report why it was out of scope.

After running Hugo commands, check that `exampleSite/public/` and `exampleSite/.hugo_build.lock` were not left in the deliverable. Remove these build artifacts before finalizing unless the user explicitly asked to keep generated output.

When delivering a full site plus theme, set the theme in site config (`theme = "<theme-name>"` or the equivalent YAML/JSON) unless the project intentionally uses `--theme` or Hugo Modules.

## UX/UI Review

Read `references/ux-ui-checklist.md` before final visual verification. Treat it as an embedded lightweight frontend-design review:
- first match the design reference;
- then check responsive behavior, accessibility, interaction states, content density, and Hugo-specific authoring ergonomics;
- do not add marketing copy or feature explanations unless the design calls for them.

Use browser screenshots when a local server can run. Prefer whatever headless browser is available in the environment, such as Playwright, Chromium/Chrome, Firefox, WebKit, or another browser already installed by the project. Check desktop and mobile widths. If Firefox on macOS is used while a regular Firefox session is open, run it with a temporary profile, for example `firefox --headless --profile /tmp/<profile> --screenshot /tmp/<theme>.png --window-size 1440,1000 <url>`. If no browser screenshot tool is available, report that visual verification was limited to Hugo build, rendered HTML, and CSS/DOM inspection. Fix text overflow, overlapping UI, broken image crops, illegible contrast, broken controls, and navigation states.

## Validation Script

Run the bundled checker from the skill directory:

```bash
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --site-dir /path/to/site
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --publication
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --mode port --publication
```

The checker emits JSON with `errors`, `warnings`, `info`, and an overall `ok` flag. Use default `--mode new` for generated variants with `exampleSite`; use `--mode port` for known-theme ports where compatibility, attribution, README/license, and original structure matter more than Hugo's generated skeleton. Add `--publication` when preparing a GitHub/public theme package. Still run Hugo itself and inspect the rendered site for visual quality.

## Completion Criteria

Finish only after:
- Hugo is installed or the user is told exactly that validation was blocked by missing Hugo;
- the changed theme builds, or remaining build failures are documented with file paths and errors;
- the design reference has been translated into maintainable Hugo templates/assets;
- theme metadata and preview-image requirements are satisfied when publication to `themes.gohugo.io` is in scope;
- UX/UI issues found during visual review are fixed or explicitly called out.
