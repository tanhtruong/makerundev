# Releasing

A published GitHub release runs `.github/workflows/release.yml`. It checks that the tag matches the `makerundev` version, runs `make check`, publishes `makerundev` and then `makerundev-server` to PyPI with trusted publishing (no API token is stored anywhere), and pushes the server image to `ghcr.io/tanhtruong/makerundev-server`.

## One-time setup

1. On pypi.org, under **Your account → Publishing → Add a new pending publisher**, register one for `makerundev-server` with the settings below. `makerundev` already has its publisher, made the same way. The first release that uploads `makerundev-server` turns its pending publisher into the project's publisher.
   - PyPI project name: `makerundev-server`
   - Owner: `tanhtruong`
   - Repository name: `makerundev`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. The `pypi` environment in the repository settings only accepts deployments from `v*` tags.

## Cutting a release

You need a clean working tree and `gh` signed in with write access. The changelog stays hand-written: everything under `## [Unreleased]` becomes the release notes, so write anything users must do before upgrading (such as backing up their data) there.

1. `make release VERSION=<version>`, for example `make release VERSION=0.3.0`. From `origin/main` it creates the branch `release/<version>`, sets `version` in both `packages/makerundev` and `apps/server` with `uv version` (which also updates `uv.lock`), pins the server's `makerundev==` requirement to the same version, moves the `[Unreleased]` entries under `## [<version>] - <today>` with a new empty `[Unreleased]` above, updates the comparison links, and opens the pull request. It refuses if `[Unreleased]` is empty, the version is not greater than the current one, or the tree has changes. To see the notes without changing anything, run `uv run python scripts/release.py prepare <version> --dry-run`.
2. Review and merge the pull request. If it merges on a later day, fix the date in `CHANGELOG.md` first.
3. `make publish`. It reads the version and that version's changelog entry from `origin/main`, shows them, asks for confirmation, and creates the GitHub release `v<version>` on that exact commit with the entry as its notes. It refuses if the tag already exists. `uv run python scripts/release.py publish --dry-run` shows what it would publish.
4. Watch the **Release** workflow. When it finishes, `pip install makerundev==<version>`, `uvx makerundev-server@<version>` and `docker pull ghcr.io/tanhtruong/makerundev-server:<version>` all work. If only the `makerundev-server` upload failed, re-run that job; the library is already on PyPI.
5. Close the version's milestone as `docs/issues.md` describes.

A version on PyPI can never be reused, so step 3 is the one that cannot be undone. The release script is `scripts/release.py`, tested in `scripts/tests/test_release.py`.

After the first image push, set the `makerundev-server` package's visibility to public under the repository's **Packages** settings, since GitHub creates new container packages as private.
