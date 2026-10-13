# Interface design

This document records the enduring visual rules of the `music-lib` interface.
It describes the purpose of the design system and how to apply it; it does not
duplicate the full list of CSS variables. **The source of truth for exact values
is [`frontend/src/styles.css`](../../frontend/src/styles.css).** If this document
and the CSS differ, follow the CSS.

## Direction

The interface is a compact work tool for managing a music collection. It uses
monospaced typography, a restrained palette, clear borders, and status colors.
High information density supports working with large lists without sacrificing
readability or discoverability of actions.

Both dark and light themes are supported. Dark theme is the default; the theme
switch is in the top bar.

## Color and states

The dark theme uses `#191919` for the background, `#21252B`, `#282C34`, and
`#2E323C` for surfaces, `#C8CCD4` for primary text, and `#61AFEF` for the accent.
The light theme uses `#F5F7FA` for the background, `#ECEFF4` and `#E2E6EC` for
surfaces, `#343B46` for text, and `#2A6FB8` for the accent.

The accent marks focus, active selection, and primary actions. Information,
warning, error, and success colors communicate state rather than decoration.
Contrast variants for light and dark themes are defined in CSS.

## Typography

The interface uses a system monospaced stack without downloaded web fonts:

```css
ui-monospace, "SF Mono", "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace
```

Hierarchy is established through size, weight, line height, and case. Headings
and technical labels are compact; body text remains large enough for extended
reading. Tabular numerals are used where numbers need to align.

## Geometry and density

- The base spacing unit is 4px; spacing levels are 4, 8, 12, 16, 24, and 32px.
- Small elements use a radius of about 6px, panels about 8px, and larger surfaces
  up to 14px. Exact tokens are in `styles.css`.
- Main content is arranged into compact panels and lists. Cards and tables must
  remain clearly grouped when displaying large amounts of data.
- The minimum touch target is set by the `--tap-min` token (44px).
- On narrow screens, the interface uses mobile navigation and panels that
  account for device safe areas.

## Surfaces and depth

Depth mainly comes from differences between the background and surfaces, along
with borders. Shadows are used for elements visually lifted from the main flow:
dialogs, floating menus, the background-task panel, and temporary notifications.
Stationary panels should not compete with content through shadows.

## Components and interaction

- **Buttons:** primary actions use the accent; secondary actions are visually
  lighter; destructive actions use the error color.
- **Inputs:** distinguish default, focused, and error states. Keyboard focus is
  visible and uses an accent ring.
- **Lists and cards:** selection and active states use a background or border,
  not only a text color change.
- **Statuses:** operation state is shown with text and an additional color or
  graphic indicator.
- **Animation:** supports feedback without interfering with lists and dialogs.
  Respect `prefers-reduced-motion`; component styles and CSS variables define
  durations and easing curves.

## Responsiveness

Wide screens use top navigation and multi-column work areas. On mobile,
navigation moves to a bottom bar with additional items in a separate menu; the
background-task panel and player are accounted for when positioning bottom
content. Resizing must not hide important actions or prevent list scrolling.

## Maintaining this document

Before changing visual tokens, check their use in `frontend/src/styles.css` and
related component styles. Do not copy the complete token list here; it quickly
drifts from the code. Update this document only when shared visual principles or
responsive behavior change.
