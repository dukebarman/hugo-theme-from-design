# Telegram Instant View Support

Use this reference only when the user asks for Telegram Instant View support, or when preparing a publishable article-focused theme where Telegram sharing matters.

## Theme Markup

- Add stable article selectors such as `article[data-iv-article]`, `.iv-title`, `[data-iv-published]`, `[data-iv-content]`, optional `[data-iv-cover]`, and `[data-iv-remove]` on UI chrome.
- Add article metadata in `head`, including canonical/description, Open Graph article fields, `og:image`, publish/modified time, author, and optional JSON-LD.
- Support front matter for author and cover/image fields.
- Add render hooks when missing: images as `figure` with captions, code blocks with language metadata, and escaped fenced code (`{{ .Inner | htmlEscape | safeHTML }}` if `safeHTML` is needed).

## Template And Docs

Include `docs/telegram-instant-view.tpl` from `assets/telegram-instant-view.tpl` when useful, adapt path rules, and document that Telegram IV must be configured and validated per live domain.

The sample template is a starting point, not a hosted service integration. Do not claim that the theme enables Instant View automatically. Site owners still need to configure and validate the template for their live domain in Telegram's editor.

Deploying or updating the Hugo theme does not enable Telegram Instant View for a site. The site owner must separately save the template in Telegram's Instant View Editor for the live domain, then validate it against real production URLs.

For multilingual Hugo sites with `defaultContentLanguageInSubdir = true`, check article URLs in every language branch. A path rule that only covers `/posts/...` will miss URLs such as `/ru/posts/...`; use a language-aware rule such as `/([a-z]{2}/)?posts/.+` or an explicit list of supported language prefixes.

Typical causes of `No Instant View available`:

- The live domain still has an older template saved in Telegram's editor.
- The `?path` rule does not cover the actual article URL, especially `/ru/posts/...` or other language-prefixed paths.
- The rendered page does not expose a required `title` or `body` selector.
- `published_date` is assigned directly from an HTML `datetime` attribute instead of converting it with `@datetime(...)` and then using `published_date: $@`.
