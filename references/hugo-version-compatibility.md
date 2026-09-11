# Hugo Version Compatibility

Reviewed through `v0.166.0` on 2026-09-11. Check `hugo version`, CI/deployment pins, and the theme's supported minimum before adopting newer APIs. Keep README and `[module.hugoVersion]` (or existing `min_version`) consistent with actual requirements. Validate the demo with the target release and, when retaining older support, the declared minimum when available.

## Hugo v0.164

- `resources.PostProcess` is deprecated. For processing that needs completed build statistics, migrate the surrounding rendering flow to `templates.Defer`; this is not a pipeline-function rename.
- `.Render` supports template subpaths and now errors when its template cannot be found. Exercise every content view used by lists and cards during migration.
- Chroma supports paired light/dark styles, including CLI generation with `hugo gen chromastyles`.

Source: [v0.164.0 release](https://github.com/gohugoio/hugo/releases/tag/v0.164.0).

Use the exact wrapper `{{ with (templates.Defer (dict "data" .)) }}...{{ end }}`, passing external context through `data`; the parentheses around the call matter. Avoid calling it through `partialCached`, including indirect calls; shortcode and render-hook use can also be unpredictable. When migrating a stats-dependent CSS pipeline, verify production output and server rebuilds after content classes change. See [templates.Defer](https://gohugo.io/functions/templates/defer/).

## Hugo v0.165

For class-based highlighting, `css.ChromaStyles` can generate CSS resources. Set `markup.highlight.noClasses = false`. For paired styles, leave the default light stylesheet unscoped and scope the dark stylesheet with `modeSelector = true`; align `classDark` with the theme's actual toggle. Retain generated static styles when supporting older Hugo. See [css.ChromaStyles](https://gohugo.io/functions/css/chromastyles/).

`importContext` lets `css.Build`, `js.Build`, `css.Sass`, and `css.PostCSS` resolve generated resources. Use it when bundling generated highlighting styles through CSS imports. Tailwind is no longer in the default `security.exec.allow` list; diagnose the actual invocation in existing Tailwind builds before changing site-specific permissions. Source: [v0.165.0 release](https://github.com/gohugoio/hugo/releases/tag/v0.165.0).

## Hugo v0.166

- `return` now follows control flow inside `if`/`range`; bare `return` can stop any template. Returning a value outside a partial errors. Preserve a single final return in partials that must support older Hugo.
- `.Render "view" $ctx` accepts custom context. Include the page explicitly in a dict if the view needs it.
- Titles containing `/` produce different automatic slugs. Compare published URLs and preserve old paths explicitly where required; taxonomy/term URLs are unaffected.
- Glob matching changed: `**/x` excludes root `x`; use `{**/,}x` for both. Check mount filters and cascade targets; malformed patterns now error.
- Symlinked mount roots are dropped. Use real directories or explicit mounts. Node tools reject links escaping permitted roots; configure only required target paths.
- Remote resource fetches reject private/local addresses with the default URL allowlist. Environment proxies require `security.http.proxyFromEnvironment = true`. Diagnose site-specific dependencies rather than adding broad theme defaults.
- Org content requires an explicit `security.allowContent` opt-in.
- `transform.ToMath` HTML/combined output requires KaTeX CSS `0.18.4+`. Update locally bundled CSS/fonts and check rendered math.

Source: [v0.166.0 release and migration notes](https://github.com/gohugoio/hugo/releases/tag/v0.166.0). Older cached documentation for `return` may still describe pre-0.166 behavior; use versioned release notes and a build with the target binary when they disagree.
