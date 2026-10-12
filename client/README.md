# Helios Clinical AI client

React, TypeScript, Vite, and Tailwind CSS v4.

## Development

From the repository root:

```sh
npm --prefix client ci
npm --prefix client run dev
```

The backend runs on port 8000; Vite proxies API requests from port 5173.
See the main documentation in `docs/README.md` for infrastructure and authentication.

## One visual source of truth

`src/globals.css` owns the entire visual theme, including fonts and shared component
styles. Sage Garden was installed with:

```sh
npx shadcn@latest add https://tweakcn.com/r/themes/sage-garden.json
```

Antic, Libre Caslon Text (the free substitute for Signifier), and JetBrains Mono
are self-hosted through Fontsource imports in that stylesheet. No font CDN is required.

- Edit `:root` for the light palette and shared typography/layout tokens.
- Edit `.dark` for the dark palette.
- `--font-sans`, `--font-serif`, and `--font-mono` select the font families.
- `--spacing`, `--radius`, and `--tracking-normal` control the global design scale.
- `--ui-text-*` controls interface text sizes; `--ui-*` controls shared layout sizes.
- `--chart-*`, `--sidebar-*`, and `--shadow-*` customize their respective surfaces.
- `--motion-fast`, `--motion-normal`, `--motion-entrance`, and `--motion-ease` control
  interaction and entrance animation timing; `--ui-lift` controls card hover lift.

Motion uses CSS transforms/opacity, with no animation runtime dependency. OS
reduced-motion preferences disable animations, transitions, and smooth scrolling.
Chat supports Enter to send, Shift+Enter for multiline questions, IME-safe input,
copy-answer feedback, and reader-controlled scroll following. Dialogs contain
keyboard focus, close with Escape, and return focus to their trigger.

## Companion experience

After sign-in, users choose Pip (cardiology), Bloom (gynaecology), Sage (internal
medicine), or Lumi (neurology). Introductions and specialty-specific prompts live
in `src/lib/companions.ts`; the backend agent IDs and specialty isolation remain
unchanged. Returning to the chooser preserves the current in-memory consultation;
choosing another specialty starts a separate workspace and aborts old requests.
Reloading does not restore the in-memory consultation.

The original mascots are inline SVG in `CompanionMascot.tsx`, not external images
or animation libraries. `globals.css` owns their paints, size, blinking, idle motion,
and hover/focus wave. Edit `--companion-pip`, `--companion-bloom`, `--companion-sage`,
`--companion-lumi`, `--companion-ink`, `--companion-size`, and
`--companion-idle-duration` to restyle them without component changes. All four
remain independently labeled keyboard-operable buttons; reduced-motion disables
their animation. They are visual assistants, not clinicians.

The consultation is an open Companion Desk: notebook-style answers, clickable
source markers, a floating question box, and a three-action bottom dock. Documents
open in a focus-contained tray rather than a permanent sidebar; evidence and
companion navigation are dock actions. Workspace health and sign-out live in the
corner menu. The welcome screen stays mascot-only, with no navbar or footer.
`--desk-reading-width`, `--desk-composer-width`, and `--desk-dock-height` customize
the shared desk geometry through `globals.css`.

All components use semantic colors rather than fixed Tailwind color families.
Recharts uses live CSS variables. Mermaid observes theme changes and CSS updates,
then regenerates its SVG using the current palette and font.

Vite reflects stylesheet edits immediately. Production needs a rebuild/deploy,
but no React code changes. Adding an entirely new font family requires importing
its font files in this same stylesheet.

## Checks

```sh
npm --prefix client run lint
npm --prefix client run test
npm --prefix client run build
```

Theme contract tests prevent hard-coded component palettes and verify that SVG
theme tokens update after CSS changes and dark-mode toggles. The existing streaming
and specialty-isolation tests remain in place.
