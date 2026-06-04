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
