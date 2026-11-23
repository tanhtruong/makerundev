# 8. React single-page app on a typed JSON API

Date: 2026-11-23

## Status

Accepted. Supersedes the front-end half of ADR 4; its data half stands.

## Context

ADR 4 chose Jinja templates and inline SVG so that the app needs no front-end build step and contributors need no JavaScript toolchain. ADR 4 expected interactive charts to need "a small client-side library later", vendored rather than loaded from a CDN.

The roadmap has outgrown that. Charts with a hover that moves across pace, heart rate and elevation together, the map under the route (ADR 9), search and filters on the activity list, and later multi-user with login all need state in the browser. Built on server-rendered pages, each would be hand-written, vendored JavaScript with no types and no tests, and those pages would keep growing. That is the worse long-term cost, even though a build step costs every contributor who touches the front-end a Node toolchain.

## Decision

- **A React single-page app replaces the Jinja pages**, page by page. A Jinja page stays until its React replacement merges.
- **Stack:** React, TypeScript, Vite, Tailwind, TanStack Router and Query, shadcn and pnpm, in `apps/web`. The folder structure follows Bulletproof React and ESLint enforces it. Charts use Recharts through shadcn's chart components. Tests use Vitest, Testing Library and MSW, and Playwright from the first page.
- **The client is generated from the API.** The server's OpenAPI schema is committed as `apps/server/openapi.json` (`make openapi`), and a test in `make check` fails when it is stale. orval generates the client's types and query hooks from it as `*.gen.ts` files.
- **The client only draws.** Every derived number is computed in tested Python and returned by the API, including chart series thinned to about 1,000 points. The client formats pace, duration, distance and local time, and nothing else.
- **Users never need Node.** `makerundev-server` on PyPI ships with the built app inside, and the Docker image builds it in a Node stage. `make check` stays Python-only, so a library contributor never installs Node.
- **No CDN and no third-party request by default.** Every asset is bundled and served by the app. A third-party request happens only when the owner opts in, as with map tiles (ADR 9).
- **No login, for now.** Unsafe requests from other sites are refused app-wide, by `Sec-Fetch-Site` or `Origin`. When multi-user login comes, it uses same-origin cookies, not bearer tokens, so that guard keeps protecting it.
- **The API convention** is written down in `docs/api.md`: a Pydantic response model, a camelCase operation id and one tag per front-end feature on every `/api` route; snake_case fields in canonical units with the unit in the name; FastAPI's error shapes; `{items, total}` lists with `limit` and `offset`; polling for live status; no version prefix before 1.0.

## Consequences

- Front-end contributors need Node and pnpm. Library and server contributors do not.
- Every page the React app shows needs a JSON endpoint first. The JSON API grows from two routes to one per page and action, each with a response model.
- `GET /api/activities` changes shape to the paged `{items, total}` envelope. `/api` is public but unversioned before 1.0, so the change is a CHANGELOG entry, not a new prefix.
- The wheel and the image grow by the built bundle, and the release builds the app before packaging the server.
- While pages are ported, the app is part Jinja and part React, and both must keep working.
