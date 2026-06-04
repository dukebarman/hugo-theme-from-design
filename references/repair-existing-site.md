# Repairing Existing Hugo Sites

Use this reference when repairing or updating an existing Hugo site that uses a theme, especially when production config, site overrides, or local visual validation are involved.

## Site Overrides Vs Theme Defaults

Identify the layer actually consumed by the template before editing copy, links, or images. Trace the value from the template expression to `.Site.Params`, `i18n`, page front matter/content, `data/`, theme defaults, or `exampleSite` config, and verify the rendered HTML after the change.

Keep site-specific copy, social links, hero/about text, profile data, and production URLs in the site layer whenever the template supports it: root config, site `i18n/`, site `content/`, or site `data/`. Change `themes/<theme>/i18n/`, default params, or theme demo content only for reusable theme defaults, fallback strings, or `exampleSite` behavior.

Do not assume editing a theme-level i18n key affects the live site; site params and site i18n can override or bypass it. If visible text is assembled from multiple params or i18n keys, such as prefix/accent/suffix hero copy, inspect the final rendered sentence in each affected language. Check grammar, punctuation, wrapping, and whether the intended key is used rather than merely present in an unused translation file.

## Local Site Validation

For visual checks of an existing site, especially when its production config has a real `baseURL`, run the local server with an explicit local base URL and in-memory rendering:

```bash
hugo server -D --bind 127.0.0.1 --baseURL http://127.0.0.1:1313/ --renderToMemory --noBuildLock
```

If the site needs an explicit theme or source path, add the existing project flags such as `--source`, `--theme`, or `--themesDir` without dropping `--baseURL http://127.0.0.1:1313/` or `--renderToMemory`. Do not trust a browser screenshot until you smoke-check that local HTML is not loading CSS, JavaScript, or image assets from the configured production host:

```bash
curl -s http://127.0.0.1:1313/ | rg "https?://<production-host>|stylesheet|script src|images/"
curl -I http://127.0.0.1:1313/css/<known-file>.css
```

For multilingual sites, smoke-check the affected language branches and pages, such as `/ru/`, `/ru/about/`, `/en/`, and `/en/about/`. Grep the rendered HTML for changed copy or links so unused params and unused i18n keys are caught before visual review.

Keep production builds separate from local server validation. Use `hugo server --renderToMemory` for visual checks, run `hugo --gc --minify` or other production builds separately, and treat generated `public/` output as build output unless the user explicitly asked to edit committed generated files.
