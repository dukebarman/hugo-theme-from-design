---
name: hugo-theme-from-design
description: Create, update, and repair Hugo themes from Figma frames, exported design assets, PNG/JPG screenshots, or existing Hugo theme repositories. Use when Codex needs to turn a website design into a Hugo theme, match a Hugo theme to a visual reference, fix Hugo layout/assets issues, scaffold with `hugo new theme`, validate theme metadata, or improve theme UX/UI against a design brief.
license: Apache-2.0
---

# Hugo Theme From Design

## Workflow

Default to generating a new theme variant from the design reference. Update or migrate an existing/old theme only when the user explicitly asks, when the task is framed as a repair, or when the repository clearly has a single theme that must be preserved.

1. Establish the target: new variant, port/reimplementation of a known theme, update to an existing theme, migration from an old theme, or repair. Identify the design source (Figma, PNG/JPG screenshot, design tokens, existing site) and the expected Hugo version/content model. Treat downloaded or user-supplied themes as a reference corpus by default: learn quality patterns from them without asking for compatibility. Ask one concise clarification only when a specific existing theme is the requested target and it is unclear whether the user wants a visually inspired new variant or a compatible port preserving that theme's public API.
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

For a new design request, create a new variant instead of overwriting an existing theme. Pick a clear variant name, scaffold or copy only what is needed, and keep the original available for comparison.

If the user asks for a port, reimplementation, migration, update, or compatibility with a named theme such as Hyde, Poole, PaperMod, or Blonde, treat it as a compatibility task. Audit and preserve the public surface where users depend on it: config params, menus, content sections, taxonomies, shortcodes/render hooks, partial extension points, assets/tooling, README/license/original metadata, and optional integrations. Do not force `exampleSite` if the target package style intentionally omits it, but provide a buildable demo when requested.

When themes are only examples, use them as a quality reference, not as a public API contract. If the target is ambiguous, state the path: compatible port preserving the original surface, or simpler visual variant. If the user says "new theme", "new variant", "test the skill", or provides only a screenshot, default to a polished new variant.

For old-theme updates, preserve URLs, front matter contracts, params, translations, shortcodes, and documented customization points unless the user approves a breaking change. Migrate template conventions only when required, update/add `exampleSite` to catch regressions, and summarize old-to-new mappings in the final answer.

## ExampleSite Generation

For every new theme variant, create `exampleSite/` inside the theme. Include config, homepage content, representative sections, menus/params/taxonomies, and enough Markdown/front matter to exercise home, list, single, taxonomy, pagination, media, navigation, footer, and long/empty states.

For reusable packages, keep demos neutral: a fictional person/studio/lab/product/venue/publication is fine, but do not make the demo a biography or portfolio of the theme author, repo owner, or user unless requested. Omit fake socials and unrelated real profiles; use RSS only or real theme-author links in footer attribution. For multilingual demos with `defaultContentLanguageInSubdir = true`, keep internal links inside the active language branch. Never leave `exampleSite/public/` or `.hugo_build.lock` in the deliverable unless requested.

## Production Readiness

For quick design tests, keep the theme focused and small. For GitHub/themes.gohugo.io publication, read `references/hugo-theme-notes.md` and add the expected package surface: README, standard license file, separate copyright/attribution notices for Apache/GPL-style licenses, theme metadata, richer `exampleSite`, preview images, favicon/webmanifest when the theme owns `<head>`, 404/RSS, responsive navigation, code styles, footer theme attribution, documented params, subpath-safe internal links/assets, and no CDN dependencies in theme-owned head output.

Do not confuse a visually plausible prototype with a reusable theme product. When the user compares against a mature human-made theme or plans to publish the result, graduate the implementation beyond screenshot matching:
- replace decorative or placeholder UI with working Hugo behavior, or remove controls that are only visual;
- implement pagination with Hugo pagination APIs when lists can exceed one page;
- use real icon assets or an icon partial instead of unicode stand-ins for reusable theme UI;
- make post images robust with page resources/static assets and resizing where practical;
- make prominent theme images replaceable. Do not hard-code hero, avatar, about, profile, or social preview paths such as `/images/specific-person.jpg` directly into templates as the only source. Read them from `params`, front matter, page resources, or data files with documented fallback defaults, for example `params.heroImage`, `params.aboutImage`, `params.avatar`, and `params.images`;
- keep user-facing URLs subpath-safe. In README examples, config params, archetypes, and front matter prefer `images/foo.jpg`, `posts/foo/`, and `tags/news/` over `/images/foo.jpg`, `/posts/foo/`, and `/tags/news/`; when template code receives a user path before `relURL`, `relLangURL`, `absURL`, or `absLangURL`, normalize accidental leading slashes so a non-root `baseURL` such as `https://example.org/blog/` still works;
- add an unobtrusive publication footer attribution for reusable themes, separate from site author/copyright: `Theme <ThemeName> by <ThemeAuthor>.` Enable it by default, make it disableable through `params.footer.showThemeAttribution`, localize the sentence through i18n, support separate `themeURL` and `themeAuthorURL`, and document the params in README;
- add search, comments, PWA, i18n, analytics, or shortcodes only when requested or implied, but make advertised features actually work;
- generate preview screenshots from the rendered theme when a browser screenshot tool is available instead of drawing schematic placeholder previews.

For publishable demo assets, exclude real people, personal identifiers, readable text, logos, trademarks, and watermarks unless the user supplied licensed assets. Compress large demo images, prefer JPEG/WebP for large illustrations, inspect favicon outputs at 32x32 and 16x16, and regenerate rendered `images/screenshot.png` and `images/tn.png` after asset changes.

## Telegram Instant View Support

When the user asks for Telegram Instant View support, or when preparing a publishable article-focused theme where Telegram sharing matters:

- Add stable article selectors such as `article[data-iv-article]`, `.iv-title`, `[data-iv-published]`, `[data-iv-content]`, optional `[data-iv-cover]`, and `[data-iv-remove]` on UI chrome.
- Add article metadata in `head`, including canonical/description, Open Graph article fields, `og:image`, publish/modified time, author, and optional JSON-LD.
- Support front matter for author and cover/image fields.
- Add render hooks when missing: images as `figure` with captions, code blocks with language metadata, and escaped fenced code (`{{ .Inner | htmlEscape | safeHTML }}` if `safeHTML` is needed).
- Include `docs/telegram-instant-view.tpl` from `assets/telegram-instant-view.tpl` when useful, adapt path rules, and document that Telegram IV must be configured and validated per live domain.

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

For publishable standalone theme packages, run publication validation before finishing; `--publication` also performs the subpath `baseURL` smoke build:

```bash
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --publication
hugo --source exampleSite --themesDir .. --theme <theme-folder-name> --destination /tmp/<theme-folder-name>-public --noBuildLock
```

Adjust `--themesDir` to the repository layout, such as `../..` when the theme lives under a site's `themes/` directory. Confirm `images/screenshot.png`, `images/tn.png`, RSS output, README, LICENSE, and `theme.toml` are present and match the advertised package surface.

After running Hugo commands, check that `exampleSite/public/` and `exampleSite/.hugo_build.lock` were not left in the deliverable. Remove these build artifacts before finalizing unless the user explicitly asked to keep generated output.

When delivering a full site plus theme, set the theme in site config (`theme = "<theme-name>"` or the equivalent YAML/JSON) unless the project intentionally uses `--theme` or Hugo Modules.

## UX/UI Review

Read `references/ux-ui-checklist.md` before final visual verification. Treat it as an embedded lightweight frontend-design review:
- first match the design reference;
- then check responsive behavior, accessibility, interaction states, content density, and Hugo-specific authoring ergonomics;
- do not add marketing copy or feature explanations unless the design calls for them.
- for generated favicon assets, inspect the 32x32 and 16x16 outputs as actual small icons; simplify or regenerate if they become indistinct blobs, lose their silhouette, or rely on text/fine detail.

Use browser screenshots when a local server can run. Check desktop and mobile widths, preflight redirects or multilingual root paths before capture, use a temporary Firefox profile if needed on macOS, and inspect screenshots before trusting them. If no browser screenshot tool is available, report that visual verification was limited to Hugo build, rendered HTML, and CSS/DOM inspection. Fix text overflow, overlap, broken crops, illegible contrast, broken controls, and navigation states.

Do not make critical hero text depend on an initial `opacity: 0` animation state for screenshot capture. Either keep essential text visible without JavaScript and animation completion, honor `prefers-reduced-motion`, or wait/disable animations in the capture path before accepting preview images.

When a local server is running and Firefox, Chrome, or Chromium is available, use the bundled screenshot helper to generate theme-store preview images from the rendered theme instead of drawing placeholder previews:

```bash
python3 scripts/render_theme_preview.py --url http://127.0.0.1:1313/ --theme-dir /path/to/theme
```

## Validation Script

Run the bundled checker from the skill directory:

```bash
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --site-dir /path/to/site
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --publication
python3 scripts/hugo_theme_check.py --theme-dir /path/to/theme --mode port --publication
```

The checker emits JSON with `errors`, `warnings`, `info`, and `ok`. Use default `--mode new` for generated variants with `exampleSite`; use `--mode port` for known-theme ports. Add `--publication` for GitHub/public packages. It warns about preview dimensions/pixel sanity, empty partials, missing package surface, subpath build failures and root-relative internal link/asset output, root-relative user/template URLs, external CDN references in theme-owned head output, nonstandard `exampleSite` `baseURL`, fake demo socials, oversized demo PNG/JPG assets, and unsafe code render hooks. Still run Hugo and inspect the rendered site for visual quality.

For skill development, run the bundled unit tests after changing scripts:

```bash
python3 -m unittest discover -s tests
```

## Completion Criteria

Finish only after:
- Hugo is installed or the user is told exactly that validation was blocked by missing Hugo;
- the changed theme builds, or remaining build failures are documented with file paths and errors;
- the design reference has been translated into maintainable Hugo templates/assets;
- theme metadata and preview-image requirements are satisfied when publication to `themes.gohugo.io` is in scope;
- UX/UI issues found during visual review are fixed or explicitly called out.
