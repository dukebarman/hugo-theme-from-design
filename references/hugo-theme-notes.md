# Hugo Theme Notes

Use this reference for Hugo-specific structure, theme publication checks, and examples to inspect.

## Current Hugo Docs Snapshot

- `hugo new theme <name>` creates a functional theme with template examples and sample content in `./themes`.
- A generated theme skeleton contains `archetypes/`, `assets/`, `content/`, `data/`, `i18n/`, `layouts/`, `static/`, and `hugo.toml`.
- Hugo's unified file system mounts theme directories onto the project. Project files take precedence over theme files at the same path.
- The official docs pages checked for this skill were built with Hugo `v0.161.1`; the relevant pages were last updated on February 25, 2026 (`hugo new theme`) and March 11, 2026 (directory structure).
- Hugo `v0.146.0` introduced a new template system. The docs say `layouts/partials` became `layouts/_partials`, `layouts/_default` was removed, and common templates moved to the `layouts/` root. Hugo preserves backward compatibility for many legacy themes, so inspect before changing conventions.

## Theme Repository Checklist

For themes intended for `themes.gohugo.io`, check:

- root `theme.toml` with name, license, licenselink, description, homepage, tags, features, and author/original metadata where applicable;
- Hugo compatibility metadata, preferably `[module.hugoVersion]` with `extended`, `min`, and optionally `max`;
- `README.md`, ideally with English documentation;
- open-source license file;
- `images/screenshot.png` or `.jpg`, 3:2 ratio, minimum `1500x1000`;
- `images/tn.png` or `.jpg`, 3:2 ratio, minimum `900x600`;
- preview images show the actual theme without browser/device mockups;
- if forked or ported, document why it is notably different and preserve original licensing requirements;
- no paid-theme gating or README-as-advertisement for a paid variant.

For ports/reimplementations of known themes:

- preserve `[original]` metadata in `theme.toml` with author/homepage/repo when the source theme is not original work;
- keep license and attribution aligned with the upstream theme;
- prefer the upstream package architecture when recognizable, such as Poole/Hyde split CSS, print/syntax CSS, theme color classes, reverse-layout params, or Hugo Module metadata;
- do not migrate legacy `_default`/`partials` structure just to satisfy new-theme conventions;
- `exampleSite` is useful but not mandatory when the port's established package style omits it. In that case, document a minimal build command or provide a separate demo site when requested.

For GitHub publication, also prefer:

- clean `.gitignore` excluding `.DS_Store`, Python caches, Hugo build output, `exampleSite/public/`, `.hugo_build.lock`, and generated resource caches;
- `README.md` with install, configuration, screenshots, exampleSite build command, and supported Hugo version;
- `LICENSE` matching `theme.toml`;
- `CHANGELOG.md` only when versioning/releasing the theme;
- favicon/webmanifest/icon assets when the theme owns head metadata;
- 404, RSS, list, single, taxonomy/term, and search/ToC/comment templates when advertised;
- mobile navigation and keyboard-accessible controls;
- code highlighting styles when sample posts include code;
- documented params such as `mainSections`, `dateFormat`, `defaultColor`, author/avatar/social fields, footer, and optional analytics/comments.

## Prototype Vs Product

A design-matching prototype can be intentionally small. A publishable theme should behave like a reusable product:

- controls visible in the UI should work, including search, color mode, mobile menu, language switcher, filters, copy buttons, and pagination;
- list pages should use `.Paginate` or a documented limit when content can grow;
- icons should come from reusable SVG assets/partials or a project icon system, not ad hoc text glyphs;
- article images should support missing images, alt text, page resources, and reasonable resizing or aspect-ratio handling;
- generated `images/screenshot.png` and `images/tn.png` should be rendered previews of the theme where possible, not schematic approximations;
- `exampleSite` should demonstrate real authoring contracts: front matter fields, taxonomies, long/short content, image/no-image cards, code blocks, and single pages;
- advertised features in `theme.toml`, README, or visible UI should be implemented and tested.

Keep optional advanced features scoped. Do not add a Tailwind/npm pipeline, search engine, comments, PWA, or multilingual system only because a comparison theme has one; add them when the design, target audience, or publishing goal benefits from the extra surface.

## Common Hugo Theme Layouts

Modern Hugo template layout:

```text
layouts/
  _markup/
  _partials/
    head.html
    header.html
    footer.html
  _shortcodes/
  baseof.html
  home.html
  page.html
  section.html
  taxonomy.html
  term.html
```

Legacy-compatible layout still common in existing themes:


```text
layouts/
  _default/baseof.html
  _default/home.html or layouts/index.html
  _default/list.html
  _default/single.html
  partials/head.html
  partials/header.html
  partials/footer.html
assets/
  css/ or scss/
  js/
static/
  favicon.ico
images/
  screenshot.png
  tn.png
theme.toml
hugo.toml, config.toml, or config/_default/*.toml
exampleSite/
  hugo.toml or config/_default/*.toml
  content/
```

Use content-type templates (`layouts/posts/list.html`, `layouts/portfolio/single.html`) only when the content model needs them. Keep generic templates in `_default`.

For new theme variants, choose the modern layout when targeting current Hugo. For existing themes, follow the existing convention unless migration is explicitly in scope.
For ports of known themes, follow the source theme's layout convention unless the user explicitly asks for modernization.

## Optional Local Examples

When a workspace includes downloaded example themes, inspect them for structure and conventions. Prefer examples that include:

- a complete `exampleSite`;
- section-specific layouts and reusable partials;
- clear theme metadata in `theme.toml`;
- modern asset handling with Hugo Pipes or a documented build pipeline.

Do not assume these paths exist in every installation, and do not copy example themes wholesale. Use available examples only for structure, partial organization, metadata, and Hugo build conventions.

## Implementation Patterns

- Distinguish real UI from presentation screenshots. If a design image shows the site inside browser chrome, a laptop/device frame, or a gradient poster background, do not put that wrapper in `baseof.html` by default. Implement the actual website surface, and use the wrapper only for generated preview images or explicit mockup pages.
- Put visual tokens in CSS custom properties or Sass variables where the existing pipeline supports it.
- Keep navigation, footer links, socials, CTA labels, and hero content configurable through site params when practical.
- Use Hugo image/resource pipelines for theme-owned assets that need fingerprinting, minification, resizing, or Sass compilation.
- Prefer semantic HTML landmarks: `header`, `nav`, `main`, `article`, `section`, `aside`, `footer`.
- Use `.IsHome`, `.Kind`, `.Section`, `.Type`, `.Params`, `.Site.Params`, menus, taxonomies, and partial dicts intentionally instead of duplicating templates.
- When the homepage design highlights a specific article/project, support an explicit front matter flag such as `featured = true` instead of assuming the latest dated content should appear first.
- Keep templates resilient when params are missing. Use `with`, `default`, and `or` where appropriate.
- Treat config params differently depending on output context: `markdownify` is appropriate for visible rich text, while metadata/attribute contexts should use plain text such as `{{ . | markdownify | plainify }}`.
- Preserve multilingual/i18n conventions if the theme has `i18n/` or language menus.
- Match base template blocks and child template definitions. If `baseof.html` exposes `{{ block "main" . }}`, each rendering template should define `{{ define "main" }}`.
- Pass context to partials explicitly: `{{ partial "header.html" . }}` or `{{ partial "card.html" (dict "page" . "featured" true) }}`. Missing context is a frequent cause of confusing template failures.
- Add or update archetypes when the design requires specific front matter such as hero image, summary, author, tags, or portfolio metadata.
- Include list/section, single/page, taxonomy/term, pagination, RSS/SEO, and 404 templates when the content model exposes those experiences.

## ExampleSite Pattern

For new variants, generate `exampleSite` inside the theme by default. Use it as the executable design proof: it should render the homepage and every major design section with representative Markdown/front matter.

Recommended structure:

```text
exampleSite/
  hugo.toml
  content/
    _index.md
    about.md or about/_index.md
    posts/
      _index.md
      example-post.md
    portfolio/ or projects/
      _index.md
      sample-project.md
```

`exampleSite/hugo.toml` should set `theme = "<theme-folder-name>"` when building with `--themesDir ..`. Include menus, taxonomies, params, language settings, and theme options that the design exposes.

Use sample content to exercise the theme:
- homepage hero and featured sections;
- list cards and single pages;
- image/no-image states;
- short and long titles;
- tags/categories and pagination when relevant;
- footer/nav/social/contact values;
- multilingual content if the design or old theme requires it.

For new themes generated from `hugo new theme`, review the root `content/` directory. The skeleton may include sample Markdown posts. Move useful examples into `exampleSite/content/` or remove them; otherwise they can leak into the demo build and distort recent-post lists.

Do not commit `exampleSite/public/` or `.hugo_build.lock` by default. They are build outputs, not theme source.

## Build Strategy

1. Run `hugo version`.
2. When scaffolding a new theme, run `hugo new theme <name>` from the site/repository root where the `themes/` directory should be created. Immediately verify the resulting path, especially if the current directory is already named `themes`, to avoid accidentally creating `themes/themes/<name>`.
3. If the theme has `exampleSite`, build it with the theme:

```bash
hugo --source exampleSite --themesDir .. --theme <theme-folder-name> --destination /tmp/<theme-folder-name>-public --noBuildLock
```

4. If working inside a full Hugo site with `themes/<theme>`, build from the site root:

```bash
hugo --theme <theme-folder-name>
```

5. For visual review, run:

```bash
hugo server --source exampleSite --themesDir .. --theme <theme-folder-name> --disableFastRender --renderToMemory --noBuildLock
```

Adjust paths to match the repository. If the existing project uses Hugo Modules instead of `themesDir`, follow its module config.
