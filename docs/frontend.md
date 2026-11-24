# The web app

The React app in `apps/web` replaces the server's Jinja pages one page at a time ([ADR 8](adr/0008-react-front-end.md)). The activity list at `/`, with the import form, was the first page, and the Strava, Garmin, training load and settings pages at `/strava`, `/garmin`, `/load` and `/settings` are ported too. The activity page at `/activities/{id}` is still Jinja until its port merges. Users never need Node: the built app ships inside the `makerundev-server` wheel and the Docker image.

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

`/api` routes and the remaining Jinja routes win. Every other `GET` path returns `index.html`, so the router handles deep links, and `/assets/*` serves the hashed build files. A path ending in `/` redirects to the same path without it. Links from React to a page that is still Jinja are plain `<a href>`, never router links, because the router does not know those pages. `src/lib/server-pages.ts` lists the paths the server still answers itself, for `make dev-web`'s proxy; porting a page removes it there, from the Jinja nav in `templates/base.html`, and from the server's routes, and its link in the top bar becomes a router link. The list also holds the server routes a React page reaches by a full page load, such as `/strava/connect`, which the Connect form posts to, and `/strava/callback`, which lands back on the React page.

## Structure

The layout follows Bulletproof React, and ESLint enforces it:

- `src/app` holds the providers, the router and the routes (TanStack Router, file-based, in `src/app/routes`).
- `src/features/<feature>` holds one feature's components and helpers. The features are `activities`, `training-load`, `settings`, `strava` and `garmin`, matching the API tags.
- `src/components`, `src/lib` and `src/testing` are shared code, and so are `src/hooks`, `src/types` and `src/utils` once something needs them. `src/components/layouts/page.tsx` gives every page its width, padding and heading.

Imports flow from shared code to features to the app. A feature never imports another feature, and shared code never imports a feature or the app. File and folder names are kebab-case, imports use `@/` rather than `../`, and there are no `index.ts` barrel files.

## The API client

orval generates the types and TanStack Query hooks from `apps/server/openapi.json` into `src/lib/api/**/*.gen.ts`. After `make openapi` changes the schema, run `pnpm generate` in `apps/web` and commit both. `make check-web` fails while they differ. Requests go through `src/lib/api-client.ts`, which throws on any non-2xx answer, so a query's error state is the request's failure.

The client only draws. Every derived number comes from the API. The client formats distance, duration, pace and local time in `src/lib/format.ts`, which matches `makerundev.format` digit for digit, ties included. Times show in the athlete's timezone from Settings, or UTC before Settings are saved, as the server counts days: a page reads it with `useTimeZone()` from `src/hooks/use-time-zone.ts` and passes it to `localDay` and `localTime`, never the browser's zone.

## Components and theme

shadcn components live in `src/components/ui` as our own code. Add one only when a page uses it, and strip its comments. The theme's tokens are in `src/styles/globals.css`, and `DESIGN.md` at the repository root describes the visual system. Light and dark follow the system setting. Fonts are bundled from `@fontsource`. The app makes no request to any other host.

## Tests

- **Component tests:** Vitest, Testing Library and MSW, next to the code they test (`*.test.ts(x)`). They run in `Europe/Copenhagen`, so time-zone bugs show.
- **End-to-end:** Playwright in `e2e/` runs each page's one path against a real server. Run `make build-web` first, since the server serves the build. Specs import `test` and `expect` from `e2e/server.ts`, which gives every test its own server on a fresh data directory and a free port, so tests run alone, in parallel, and beside other checkouts' servers. Fixtures are generated in the test, such as `gpx()` in `e2e/gpx.ts`.
  - By default the server is the app itself (`makerundev_server.app:create_app`).
  - A page that talks to an outside service runs against a launcher in `apps/server/tests` instead, never the live service. A launcher is a module with a factory that builds the app with that service's fake as its transport, such as `garmin_e2e_server.py` with `def create() -> FastAPI`. The spec picks it with `test.use({ app: "garmin_e2e_server:create" })`, and `serverEnv` adds environment variables such as client credentials.
  - The launcher reads the data directory through `create_app`'s default, and the fixture sets the host and port. To time a transient state, the launcher holds the fake's response on a `threading.Event` and adds a test-only `POST` route that sets it, such as `POST /e2e/garmin/release` (a `GET` route added after `create_app` loses to the web app's catch-all), which the spec calls with `request.post` once it has asserted the state.
