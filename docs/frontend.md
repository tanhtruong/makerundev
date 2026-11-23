# The web app

The React app in `apps/web` replaces the server's Jinja pages one page at a time ([ADR 8](adr/0008-react-front-end.md)). The activity list at `/` is the first page. Every other page is still Jinja until its port merges. Users never need Node: the built app ships inside the `makerundev-server` wheel and the Docker image.

## Set up

You need Node (the version in `apps/web/.nvmrc`) and pnpm. Corepack installs the pnpm version pinned in `apps/web/package.json`:

```bash
corepack enable
```

```bash
make sync-web
```

Python-only work needs none of this. `make sync` and `make check` never touch Node. Without a build, the server answers the React routes with a "UI not built: run `make build-web`" page, and the Jinja pages and the JSON API work as before.

## Commands

| Command | What it does |
| --- | --- |
| `make sync-web` | Install the locked dependencies |
| `make dev-web` | Vite on http://localhost:5173, with `/api`, `/static` and the remaining Jinja pages proxied to `make serve` on port 8000 |
| `make build-web` | Typecheck and build into `apps/server/src/makerundev_server/web/`, which the server serves |
| `make check-web` | ESLint, Prettier, `tsc`, Vitest, a check that the generated files are fresh, a build, and Playwright |

Inside `apps/web`, `pnpm generate` regenerates the API client and `pnpm format` applies Prettier and ESLint fixes.

## How the server serves it

`/api` routes and the remaining Jinja routes win. Every other `GET` path returns `index.html`, so the router handles deep links, and `/assets/*` serves the hashed build files. A path ending in `/` redirects to the same path without it. Links from React to a page that is still Jinja are plain `<a href>`, never router links, because the router does not know those pages. `src/lib/server-pages.ts` lists those pages once, for the top bar and for `make dev-web`'s proxy; porting a page removes it there, from the Jinja nav in `templates/base.html`, and from the server's routes.

## Structure

The layout follows Bulletproof React, and ESLint enforces it:

- `src/app` holds the providers, the router and the routes (TanStack Router, file-based, in `src/app/routes`).
- `src/features/<feature>` holds one feature's components and helpers. The features are `activities`, `training-load`, `settings`, `strava` and `garmin`, matching the API tags.
- `src/components`, `src/lib` and `src/testing` are shared code, and so are `src/hooks`, `src/types` and `src/utils` once something needs them. `src/components/layouts/page.tsx` gives every page its width, padding and heading.

Imports flow from shared code to features to the app. A feature never imports another feature, and shared code never imports a feature or the app. File and folder names are kebab-case, imports use `@/` rather than `../`, and there are no `index.ts` barrel files.

## The API client

orval generates the types and TanStack Query hooks from `apps/server/openapi.json` into `src/lib/api/**/*.gen.ts`. After `make openapi` changes the schema, run `pnpm generate` in `apps/web` and commit both. `make check-web` fails while they differ. Requests go through `src/lib/api-client.ts`, which throws on any non-2xx answer, so a query's error state is the request's failure.

The client only draws. Every derived number comes from the API. The client formats distance, duration, pace and local time in `src/lib/format.ts`, which matches `makerundev.format` digit for digit, ties included. Times show in the browser's time zone until the settings API exposes the athlete's own.

## Components and theme

shadcn components live in `src/components/ui` as our own code. Add one only when a page uses it, and strip its comments. The theme's tokens are in `src/styles/globals.css`, and `DESIGN.md` at the repository root describes the visual system. Light and dark follow the system setting. Fonts are bundled from `@fontsource`. The app makes no request to any other host.

## Tests

- **Component tests:** Vitest, Testing Library and MSW, next to the code they test (`*.test.ts(x)`). They run in `Europe/Copenhagen`, so time-zone bugs show.
- **End-to-end:** Playwright in `e2e/` runs each page's one path against a real `makerundev-server` on a fresh data directory, with fixtures generated in the test. Run `make build-web` first, since the server serves the build.
