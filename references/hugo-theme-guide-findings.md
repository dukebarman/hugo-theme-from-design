# Hugo Theme Guide Findings

Use this distilled checklist when comparing this skill against common Hugo theme tutorials and third-party guides.

## Repeated Tutorial Pattern

Popular guides converge on this sequence:

1. Install/check Hugo.
2. Create a site and a theme with `hugo new site` and `hugo new theme`.
3. Set the site config to use the new theme.
4. Build the global shell with a base template.
5. Add home, list/section, and single/page templates.
6. Split repeated header, footer, head, navigation, and cards into partials.
7. Add styles through `static/` for copied files or `assets/` for Hugo Pipes.
8. Add `exampleSite` sample config/content, archetypes, taxonomies, pagination, and SEO/RSS where the theme type needs them.
9. Run `hugo server` continuously and fix lookup/build errors early.

For this skill, apply that pattern to a new variant by default. Treat direct updates to an old theme as a migration path with compatibility constraints, not as the default action.
For new variants, `exampleSite` is part of the deliverable, not an optional extra.
For ports/reimplementations of known themes, preserve upstream package conventions and attribution even when they differ from new-variant defaults.

## Tutorial-Specific Signals

- Brian Wagner's step-by-step guide emphasizes boilerplate generation, assigning the theme in config, editing `baseof.html`, defining `main` blocks in child templates, adding list/single templates, navigation, and stylesheets.
- Draft.dev's guide frames custom themes around brand control, navigation, content organization, blog post templates, multi-author data, pagination, taxonomies, and SEO.
- Tomo's Hugo theme series highlights Go template syntax, context (`.` and `$`), pipelines, directory roles, page kinds, Tailwind, dark mode, responsive design, multilingual support, code highlighting, CI, official theme submission, and SEO.
- CloudCannon's partials tutorial highlights DRY partials and explicitly passing context with `.` when a partial needs page data.
- PäksTech's guide explains archetypes, `baseof.html`, partials, and the difference between layout files and copied/processed assets.
- Older Hugo tutorials often use `layouts/_default` and `layouts/partials`; current Hugo docs for `v0.146+` prefer root templates and `layouts/_partials`. Preserve legacy conventions in existing themes and use modern conventions for new themes unless project constraints say otherwise.

## Gaps To Check In A Generated Theme

- Did the implementation accidentally turn screenshot presentation chrome (browser frame, device mockup, gradient wallpaper) into live site UI?
- Does the site config actually select the theme, or do docs/commands require `--theme`?
- If this is a known-theme port, does `theme.toml` include original metadata and does the implementation preserve recognizable upstream params/assets/layout conventions?
- Does every child template define the blocks expected by the base template?
- Are partials passed the context they need?
- Are home, page/single, section/list, taxonomy/term, RSS, 404, and pagination covered when relevant?
- If the design shows a specific homepage item, is that controlled by front matter/config rather than accidentally relying on date order?
- Are archetypes aligned with the front matter the design expects?
- Are Markdown-enabled params sanitized before being used in meta tags or HTML attributes?
- Does `exampleSite` demonstrate the design with real sections, config params, menus, and content states?
- Did `hugo new theme` leave sample Markdown in root `content/` that should be moved to `exampleSite/content/` or removed?
- Are `exampleSite/public/` and `.hugo_build.lock` absent from the source deliverable?
- Are authoring-facing params documented through sample config or README, not buried in templates?
- If intended for GitHub/public release, are README, LICENSE, screenshots, 404/RSS, favicon/webmanifest, mobile navigation, code styling, footer theme attribution, and documented params present?
- Does the theme work under a non-root `baseURL` using relative/permalink-safe asset paths?
