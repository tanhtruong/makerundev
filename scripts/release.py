from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("pacelab", "pacelab-server")
LIBRARY_PYPROJECT = "packages/pacelab/pyproject.toml"
CHANGELOG = "CHANGELOG.md"
REPO_URL = "https://github.com/tanhtruong/pacelab"

_VERSION = re.compile(r"\d+\.\d+\.\d+")
_SECTION = re.compile(r"^## \[(?P<name>[^\]]+)\](?P<date>.*)$", re.MULTILINE)
_UNRELEASED_LINK = re.compile(
    r"^\[Unreleased\]: (?P<base>\S+)/compare/v(?P<previous>\d+\.\d+\.\d+)\.\.\.HEAD$",
    re.MULTILINE,
)


class ReleaseError(Exception):
    pass


def parse_version(text: str) -> tuple[int, int, int]:
    if not _VERSION.fullmatch(text):
        raise ReleaseError(f"{text!r} is not a version like 0.3.0")
    major, minor, patch = (int(part) for part in text.split("."))
    return major, minor, patch


def check_bump(current: str, new: str) -> None:
    if parse_version(new) <= parse_version(current):
        raise ReleaseError(f"{new} is not greater than the current version {current}")


def _sections(text: str) -> dict[str, tuple[int, int, str]]:
    matches = list(_SECTION.finditer(text))
    links = re.search(r"^\[[^\]]+\]: ", text, re.MULTILINE)
    end_of_entries = links.start() if links else len(text)
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else end_of_entries
        sections[match["name"]] = (match.end(), end, match["date"].strip())
    return sections


def roll_changelog(text: str, version: str, date: dt.date) -> str:
    sections = _sections(text)
    if "Unreleased" not in sections:
        raise ReleaseError("CHANGELOG.md has no ## [Unreleased] section")
    if version in sections:
        raise ReleaseError(f"CHANGELOG.md already has a section for {version}")
    start, end, _ = sections["Unreleased"]
    if not text[start:end].strip():
        raise ReleaseError("## [Unreleased] in CHANGELOG.md is empty; nothing to release")
    link = _UNRELEASED_LINK.search(text)
    if link is None:
        raise ReleaseError(
            "CHANGELOG.md has no [Unreleased]: <repo>/compare/v<previous>...HEAD link"
        )
    base, previous = link["base"], link["previous"]
    check_bump(previous, version)

    text = text[:start] + f"\n\n## [{version}] - {date.isoformat()}" + text[start:]
    return text.replace(
        link.group(0),
        f"[Unreleased]: {base}/compare/v{version}...HEAD\n"
        f"[{version}]: {base}/compare/v{previous}...v{version}",
    )


def release_notes(text: str, version: str) -> str:
    sections = _sections(text)
    if version not in sections:
        raise ReleaseError(f"CHANGELOG.md has no section for {version}")
    start, end, date = sections[version]
    if not date.startswith("- "):
        raise ReleaseError(f"## [{version}] in CHANGELOG.md has no date; run prepare first")
    notes = text[start:end].strip()
    if not notes:
        raise ReleaseError(f"## [{version}] in CHANGELOG.md is empty")
    return notes + "\n"


def _run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=capture)
    if result.returncode != 0:
        detail = f": {result.stderr.strip()}" if capture and result.stderr else ""
        raise ReleaseError(f"`{' '.join(args)}` failed{detail}")
    return result.stdout.strip() if capture else ""


def _git(*args: str) -> str:
    return _run("git", *args, capture=True)


def _library_version(pyproject: str) -> str:
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    if match is None:
        raise ReleaseError(f"no version in {LIBRARY_PYPROJECT}")
    return match.group(1)


def prepare(version: str, *, dry_run: bool) -> None:
    parse_version(version)
    if _git("status", "--porcelain"):
        raise ReleaseError(
            "the working tree has changes; commit them or start from a clean checkout"
        )
    _git("fetch", "origin", "--quiet")
    branch = f"release/{version}"
    current = _library_version(_git("show", f"origin/main:{LIBRARY_PYPROJECT}"))
    check_bump(current, version)
    changelog = _git("show", f"origin/main:{CHANGELOG}") + "\n"
    if f"/compare/v{current}...HEAD" not in changelog:
        raise ReleaseError(
            f"the [Unreleased] link in CHANGELOG.md does not compare from v{current}"
        )
    changelog = roll_changelog(changelog, version, dt.date.today())

    if dry_run:
        print(f"Would bump {', '.join(PACKAGES)} from {current} to {version}")
        print(f"Would open a pull request from {branch}. Release notes:\n")
        print(release_notes(changelog, version))
        return

    _git("switch", "--quiet", "--create", branch, "--no-track", "origin/main")
    for package in PACKAGES:
        _run("uv", "version", "--package", package, version, "--no-sync", capture=True)
    (ROOT / CHANGELOG).write_text(changelog)
    _git("commit", "--quiet", "--all", "--message", f"chore: release {version}")
    _git("push", "--quiet", "--set-upstream", "origin", branch)
    url = _run(
        "gh", "pr", "create", "--base", "main", "--head", branch,
        "--title", f"chore: release {version}",
        "--body", _pull_request_body(version, current),
        capture=True,
    )  # fmt: skip
    print(f"Opened {url}")
    print(f"You are on {branch}. When it is merged, run `make publish`.")


def _pull_request_body(version: str, previous: str) -> str:
    return (
        f"Release {version}, prepared by `make release`.\n\n"
        f"- `pacelab` and `pacelab-server`: {previous} -> {version}, `uv.lock` updated\n"
        f"- `CHANGELOG.md`: [Unreleased] is now [{version}] - {dt.date.today().isoformat()}\n\n"
        "Check the changelog entry reads well as release notes, and update its date if this "
        "merges on a later day. After merging, run `make publish`.\n"
    )


def publish(*, yes: bool, dry_run: bool) -> None:
    _git("fetch", "origin", "--quiet", "--tags")
    sha = _git("rev-parse", "origin/main")
    version = _library_version(_git("show", f"{sha}:{LIBRARY_PYPROJECT}"))
    tag = f"v{version}"
    notes = release_notes(_git("show", f"{sha}:{CHANGELOG}"), version)
    if _git("ls-remote", "--tags", "origin", f"refs/tags/{tag}"):
        raise ReleaseError(f"{tag} already exists; bump the version with `make release` first")

    print(f"{tag} at origin/main {sha[:7]}, with these release notes:\n\n{notes}")
    if dry_run:
        print(f"Would create the GitHub release {tag}, which publishes to PyPI and GHCR.")
        return
    if not yes:
        if not sys.stdin.isatty():
            raise ReleaseError("not a terminal; pass --yes to publish without asking")
        answer = input(f"Publish {tag} to PyPI and GHCR? This cannot be undone. [y/N] ")
        if answer.strip().lower() != "y":
            print("Nothing published.")
            return

    with tempfile.NamedTemporaryFile("w", suffix=".md") as notes_file:
        notes_file.write(notes)
        notes_file.flush()
        url = _run(
            "gh", "release", "create", tag, "--target", sha,
            "--title", tag, "--notes-file", notes_file.name,
            capture=True,
        )  # fmt: skip
    print(f"Published {url}")
    print(f"Watch the Release workflow: {REPO_URL}/actions/workflows/release.yml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cut a pacelab release, see docs/releasing.md")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="bump versions and open the release PR")
    prepare_parser.add_argument("version", help="the new version, for example 0.3.0")
    prepare_parser.add_argument("--dry-run", action="store_true", help="show what would change")
    publish_parser = commands.add_parser("publish", help="create the GitHub release from main")
    publish_parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    publish_parser.add_argument("--dry-run", action="store_true", help="show what would publish")
    args = parser.parse_args(argv)

    try:
        if args.command == "prepare":
            prepare(args.version, dry_run=args.dry_run)
        else:
            publish(yes=args.yes, dry_run=args.dry_run)
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
