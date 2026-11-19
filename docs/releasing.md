# Releasing

A published GitHub release runs `.github/workflows/release.yml`. It checks that the tag matches the `pacelab` version, runs `make check`, publishes the library to PyPI with trusted publishing (no API token is stored anywhere), and pushes the server image to `ghcr.io/tanhtruong/pacelab-server`.

## One-time setup

1. On pypi.org, under **Your account → Publishing → Add a new pending publisher**, register:
   - PyPI project name: `pacelab`
   - Owner: `tanhtruong`
   - Repository name: `pacelab`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. The `pypi` environment in the repository settings only accepts deployments from `v*` tags.

## Cutting a release

1. In one pull request, bump `version` in `packages/pacelab/pyproject.toml` and, in `CHANGELOG.md`, rename `[Unreleased]` to `[<version>] - <YYYY-MM-DD>`, start a new empty `[Unreleased]` section above it, and update the comparison links at the bottom. Merge it.
2. Create a release on GitHub with a new tag `v<version>` on `main`, for example `v0.1.0`, paste that version's changelog entry as the release notes, and publish it.
3. Watch the **Release** workflow. When it finishes, `pip install pacelab==<version>` and `docker pull ghcr.io/tanhtruong/pacelab-server:<version>` both work.

After the first image push, set the `pacelab-server` package's visibility to public under the repository's **Packages** settings, since GitHub creates new container packages as private.
