# Contributing to pacelab

Thanks for helping. Bug reports, file-format edge cases, metric ideas and code are all welcome.

## Set up

Contributions come in through forks: only maintainers can push branches to this repository. Fork pacelab on GitHub, then:

```bash
git clone https://github.com/<your-username>/pacelab.git
cd pacelab
git remote add upstream https://github.com/tanhtruong/pacelab.git
uv sync
make check
```

`make check` runs ruff, mypy (strict) and the test suite. CI runs the same command.

## Reporting a parsing bug

The most useful report includes the file that fails. Activity files contain GPS tracks, so strip or shift the positions first, or describe the device, firmware and export path so we can reproduce it with a generated file.

## Changing a metric

Metric definitions are part of the public contract. A change needs:

1. The definition updated in `GLOSSARY.md`.
2. A test in `packages/pacelab/tests/test_metrics.py` with hand-computed expected values, seen failing before the change.
3. A note in the pull request on how results shift for existing users.
4. An entry under `[Unreleased]` in `CHANGELOG.md` saying the same.

## Pull requests

1. Start a branch in your fork from the latest `main`:

   ```bash
   git fetch upstream
   git switch -c fix/tcx-lap-times upstream/main
   ```

2. Run `make check`, push the branch to your fork, and open a pull request against `main` here.
3. Leave **Allow edits by maintainers** ticked, so we can update your branch or push small fixes.
4. CI must pass and review threads must be resolved before merging. Pull requests are squash-merged, so the pull request title becomes the commit message on `main`.

Guidelines:

- One concern per pull request.
- Pull request titles and commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(metrics): add grade-adjusted pace`.
- UI changes include before and after screenshots.
- New decisions that are hard to reverse get an ADR in `docs/adr/`.

By contributing you agree that your contributions are licensed under the Apache License 2.0.
