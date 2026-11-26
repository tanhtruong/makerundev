.PHONY: sync check lint format types test openapi serve demo release publish sync-web build-web check-web dev-web

sync:
	uv sync --locked

check: lint types test

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

types:
	uv run mypy

test:
	uv run pytest -q

openapi:
	uv run python scripts/openapi.py

sync-web:
	cd apps/web && pnpm install --frozen-lockfile

build-web:
	cd apps/web && pnpm build

check-web:
	cd apps/web && pnpm lint && pnpm typecheck && pnpm test
	cd apps/web && pnpm generate && pnpm exec vite build
	@test -z "$$(git status --porcelain -- apps/web/src/lib/api apps/web/src/app/route-tree.gen.ts)" \
		|| { git status --short -- apps/web/src; echo "generated web files are stale: commit what make check-web wrote" >&2; exit 1; }
	cd apps/web && pnpm e2e

dev-web:
	cd apps/web && pnpm dev

serve:
	uv run makerundev-server

demo:
	@test -n "$(DATA_DIR)" || { echo "usage: make demo DATA_DIR=<empty dir> [SEED=n] [END=yyyy-mm-dd]" >&2; exit 1; }
	uv run python scripts/demo.py "$(DATA_DIR)" $(if $(SEED),--seed $(SEED)) $(if $(END),--end $(END))

release:
	@test -n "$(VERSION)" || { echo "usage: make release VERSION=x.y.z" >&2; exit 1; }
	uv run python scripts/release.py prepare $(VERSION)

publish:
	uv run python scripts/release.py publish
