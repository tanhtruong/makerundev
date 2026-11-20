.PHONY: sync check lint format types test serve release publish

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

serve:
	uv run pacelab-server

release:
	@test -n "$(VERSION)" || { echo "usage: make release VERSION=x.y.z" >&2; exit 1; }
	uv run python scripts/release.py prepare $(VERSION)

publish:
	uv run python scripts/release.py publish
