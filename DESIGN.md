---
version: "alpha"
name: OAK Trading Terminal
description: A compact, high-contrast operations shell for MT5 monitoring and trade control.
colors:
  primary: "#050806"
  surface: "#0D1412"
  surface-raised: "#101615"
  ink: "#04130F"
  text: "#F6FFF9"
  text-muted: "#8E9A96"
  accent: "#00C991"
  accent-strong: "#00D19A"
  warning: "#F4B740"
  danger: "#FF5364"
  outline: "rgba(255,255,255,24)"
typography:
  display:
    fontFamily: "Segoe UI"
    fontSize: 52px
    fontWeight: 900
    lineHeight: 1.05
    letterSpacing: -2px
  section:
    fontFamily: "Segoe UI"
    fontSize: 22px
    fontWeight: 900
    lineHeight: 1.2
  body:
    fontFamily: "Segoe UI"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Segoe UI"
    fontSize: 11px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 2px
  value:
    fontFamily: "Consolas"
    fontSize: 28px
    fontWeight: 900
    lineHeight: 1.1
rounded:
  xs: 6px
  sm: 8px
  md: 14px
  lg: 18px
  xl: 24px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 18px
  xl: 24px
  xxl: 28px
components:
  app-shell:
    backgroundColor: "{colors.primary}"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.xl}"
    padding: "{spacing.xl}"
  row:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  select-menu:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
  status-positive:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.ink}"
  status-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.ink}"
  status-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.ink}"
  metadata:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
---

## Overview

OAK is a focused trading terminal, not a consumer dashboard. The visual language is a dark premium terminal with a single operational accent. Every surface should make monitoring status and operator actions easier to scan.

## Colors

`primary` is the near-black application field. `surface` and `surface-raised` separate panels without gradients that obscure operational data. `accent` is reserved for active navigation, safe primary actions, and healthy states. Amber and red communicate warning and stop conditions only.

## Typography

Use Segoe UI for interface copy and Consolas for values, timestamps, prices, tickets, and operational state. Titles are large but limited to the hero area. Labels use sparse uppercase tracking for scanability; do not apply uppercase styling to paragraph text.

## Layout

Use the spacing scale only. The desktop shell has an 18px outer rhythm, 260px navigation rail, and wide content panes. Group related controls inside a single panel before adding another panel. Preserve a clear reading order: status, action, then detail.

## Elevation & Depth

Depth comes from subtle surface contrast and a one-pixel outline, never large shadows. The background may use a restrained green radial bloom, but cards remain matte and legible.

## Shapes

Panels use `xl`, information rows and buttons use `md`, and tightly grouped controls use `sm`. Do not mix unrelated radii in the same component.

## Components

Use the tokenized panel, row, button, select-menu, and status styles. Native Qt combo popups must explicitly style both the menu and each option so Windows never falls back to a white system list.

## Do's and Don'ts

- Do use one primary action per operator task.
- Do keep credentials masked and destructive controls guarded.
- Do keep contrast at WCAG AA or better for text and actionable controls.
- Do not introduce browser runtimes, WebEngine, or decorative animation into the NativeQt build.
- Do not use green for passive copy, labels, or inactive cards.
- Do not add cards merely to fill space; every panel must expose a live state, an action, or a decision.
