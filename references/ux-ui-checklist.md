# UX/UI Checklist For Hugo Themes

Use this as a lightweight embedded frontend-design review when translating a Figma frame or screenshot into a Hugo theme.

## Visual Match

- Compare the rendered page to the reference at equivalent viewport widths.
- Preserve hierarchy: primary action, page title, section rhythm, density, and reading order.
- Match type scale by role, not by copying oversized text everywhere.
- Keep spacing systematic. Repeated components should share the same padding, gaps, radii, and media ratios.
- Use real design assets when available. Do not hide weak asset handling behind dark overlays, blur, or generic gradients.

## Responsive Behavior

- Check at least mobile, tablet or narrow desktop, and wide desktop.
- Ensure navigation has a real mobile state.
- Ensure long titles, menu labels, tags, dates, and author names wrap cleanly.
- Define stable dimensions for repeated cards, image containers, icon buttons, and toolbars.
- Do not let hover/focus/loading states resize layouts.

## Accessibility

- Use semantic HTML and one logical `h1` per page.
- Keep text contrast legible in light and dark modes.
- Add useful alt text for content images and empty alt for decorative images.
- Ensure keyboard focus is visible on links, buttons, menus, search, toggles, and pagination.
- Respect reduced motion when adding transitions or animations.

## Content And Authoring

- Test empty, short, and long content states.
- Do not hard-code page copy that should come from Markdown front matter or site params.
- Keep cards and lists useful when summaries, dates, images, tags, or authors are missing.
- Make taxonomy, pagination, RSS, 404, and single/list pages feel like the same design system.

## Hugo-Specific UX Risks

- Asset paths must work when the site is deployed under a non-root `baseURL`.
- Menus should use Hugo menu APIs or documented params, not fixed links only.
- Images should resolve from page resources, `assets/`, or `static/` consistently.
- Theme defaults should render a credible page before the user customizes every param.
- Documentation and sample config should expose key design options without forcing users to edit templates.

## Final Visual Pass

Before finishing, look for:

- overlapping text or controls;
- clipped cards, images, code blocks, tables, and pagination;
- unreadable nav over hero media;
- inconsistent icon sizes;
- missing hover/focus/active states;
- one-color palettes that make hierarchy unclear;
- decorative UI that competes with content.
