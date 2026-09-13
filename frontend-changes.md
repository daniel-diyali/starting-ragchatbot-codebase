# Frontend Changes: Dark/Light Theme Toggle

## Summary

Added a dark/light theme toggle button to the Course Materials Assistant UI. The app previously had a single, hardcoded dark theme; it now defaults to dark (or the user's system preference on first visit) and lets the user switch themes at any time, with the choice persisted across reloads.

## Files Changed

- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

## Details

### `index.html`

- Added a `<button id="themeToggle" class="theme-toggle">` as the first element in `<body>`, fixed to the top-right corner so it's positioned consistently regardless of the (currently hidden) header.
- The button contains two inline SVG icons — a sun and a moon — layered on top of each other; CSS shows/hides them based on the active theme.
- `aria-label`, `aria-pressed`, and `title` attributes are set on the button and kept in sync with the current theme by JS, so screen readers announce both the button's purpose and its current state.
- Both icons are `aria-hidden="true"` since the button's `aria-label` already conveys the action.
- Bumped the cache-busting query strings on `style.css` and `script.js`.

### `style.css`

- Added a `body[data-theme="light"]` block that overrides the existing CSS custom properties (`--background`, `--surface`, `--text-primary`, `--border-color`, etc.) with a light palette. The dark palette already defined on `:root` remains the default, so no existing look changes unless the light theme is active.
- Added `.theme-toggle` styles: fixed position (`top: 1.25rem; right: 1.25rem`), circular button matching the app's existing surface/border/shadow language, hover/active/focus-visible states consistent with other buttons in the app (e.g. `#sendButton`).
- Added `.theme-icon` rules that crossfade and rotate the sun/moon icons (`opacity` + `rotate/scale` transform, `0.3s`–`0.4s` ease) so switching themes animates smoothly instead of snapping.
- Added a `transition: background-color/border-color/color/box-shadow` rule to the main surfaces (sidebar, chat panes, messages, input, buttons, pills) so the whole UI fades between palettes instead of flashing.
- Added a small media-query tweak to shrink/reposition `.theme-toggle` on narrow (≤768px) viewports.

### `script.js`

- Added `themeToggle` to the cached DOM elements.
- `initTheme()` (called on `DOMContentLoaded`): reads a saved theme from `localStorage`, falling back to the OS-level `prefers-color-scheme: light` media query, falling back to dark; applies it via `applyTheme()`.
- `toggleTheme()`: flips between `light`/`dark` and persists the choice to `localStorage` under the `theme` key.
- `applyTheme(theme)`: sets/removes `data-theme="light"` on `<body>` (dark needs no attribute, matching the existing default palette) and updates the button's `aria-pressed`/`aria-label`.
- Wired `themeToggle`'s `click` event in `setupEventListeners()`. No extra keyboard handling was needed — it's a native `<button>`, so Enter/Space and Tab focus work out of the box; verified via the browser's accessibility tree.

## Verification

Served the frontend locally and drove it with Playwright:
- Confirmed the button renders top-right in both themes, the sun/moon icons crossfade correctly, and colors across the sidebar, chat area, input, and buttons transition smoothly.
- Confirmed keyboard access: `Tab`/`Shift+Tab` reaches the button in the natural DOM order, and `Enter` toggles the theme, matching the visible focus ring.
- Confirmed `aria-pressed` and `aria-label` update correctly ("Switch to light theme" ↔ "Switch to dark theme").

---

## Follow-up: Light Theme Palette Refinement

Reviewed the `body[data-theme="light"]` palette (`frontend/style.css:28-43`) against the specific requirements below and tightened one value.

### Palette

| Token | Dark (unchanged) | Light | Notes |
|---|---|---|---|
| `--background` | `#0f172a` | `#f8fafc` | Page background — light, slightly cool off-white |
| `--surface` | `#1e293b` | `#ffffff` | Cards, bubbles, inputs |
| `--surface-hover` | `#334155` | `#e2e8f0` | Hover state for surfaces |
| `--text-primary` | `#f1f5f9` | `#0f172a` | Body/heading text — near-black for max contrast |
| `--text-secondary` | `#94a3b8` | `#52606d` | Muted labels/metadata — darkened, not just inverted, to stay readable on light backgrounds |
| `--border-color` | `#334155` | `#b0bccb` | Dividers, input/card outlines (see fix below) |
| `--primary-color` / `--primary-hover` | `#2563eb` / `#1d4ed8` | unchanged | Brand blue already passes AA on both light and dark surfaces, so it's kept consistent rather than re-tuned per theme |
| `--user-message` | `#2563eb` | unchanged | User bubble fill |
| `--assistant-message` | `#374151` | `#eef2f7` | Assistant bubble fill (not directly applied to `.message-content`, but kept for consistency) |
| `--welcome-bg` / `--welcome-border` | `#1e3a5f` / `#2563eb` | `#e0ecff` / `#2563eb` | Welcome-card accent |
| `--focus-ring` | `rgba(37,99,235,0.2)` | `rgba(37,99,235,0.25)` | Bumped opacity slightly so the focus ring stays visible against light surfaces |
| `--shadow` | `0 4px 6px -1px rgba(0,0,0,0.3)` | `0 4px 6px -1px rgba(15,23,42,0.1)` | Lightened so card shadows don't look muddy on a white background |

### Accessibility check (WCAG contrast ratios, computed against the actual light-theme hex values)

| Pair | Ratio | WCAG AA target | Result |
|---|---|---|---|
| `--text-primary` on `--background` | 17.06:1 | 4.5:1 (text) | Pass (AAA) |
| `--text-primary` on `--surface` | 17.85:1 | 4.5:1 | Pass (AAA) |
| `--text-secondary` on `--background` | 6.17:1 | 4.5:1 | Pass |
| `--text-secondary` on `--surface` | 6.46:1 | 4.5:1 | Pass |
| `--primary-color` text on `--background` | 4.94:1 | 4.5:1 | Pass |
| White text on `--primary-color` (buttons) | 5.17:1 | 4.5:1 | Pass |
| `--welcome-border` on `--welcome-bg` | 4.33:1 | 3:1 (non-text) | Pass |

**Fix applied:** `--border-color` on `--surface` was only **1.48:1**. In light mode, `--surface` (`#ffffff`) and `--background` (`#f8fafc`) are nearly identical, so elements like `#chatInput` and the stat/suggested cards rely on their border as the *only* visible boundary — that's the case WCAG 1.4.11 (non-text contrast, 3:1 target for essential UI boundaries) is aimed at. Darkened `--border-color` from `#cbd5e1` to `#b0bccb`, raising that ratio to **1.93:1** — a meaningful improvement while keeping the theme visually light and consistent with the existing "subtle divider" aesthetic used throughout the app. Pushing all the way to a strict 3:1 (~`#919191`) would have made every hairline divider in the app look heavy, so this was a deliberate balance between the airy light aesthetic and boundary legibility; the chat input and buttons also carry a distinct `:focus` border/box-shadow, so keyboard/focus visibility does not depend on the resting border alone.

### Verification

Reloaded the app with `localStorage.theme = 'light'` forced and Playwright screenshots confirmed: light background, dark high-contrast text, visible (but still subtle) borders on the chat input and welcome card, and the toggle button/icon rendering correctly on a light background.
