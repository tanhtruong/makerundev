import datetime as dt

import pytest
from release import ReleaseError, check_bump, release_notes, roll_changelog

BEFORE = """\
# Changelog

Intro.

## [Unreleased]

### Added

- Training load page.

## [0.1.0] - 2026-11-19

### Added

- Parsers.

[Unreleased]: https://github.com/o/r/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/o/r/releases/tag/v0.1.0
"""

AFTER = """\
# Changelog

Intro.

## [Unreleased]

## [0.2.0] - 2026-11-20

### Added

- Training load page.

## [0.1.0] - 2026-11-19

### Added

- Parsers.

[Unreleased]: https://github.com/o/r/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/o/r/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/o/r/releases/tag/v0.1.0
"""

DAY = dt.date(2026, 11, 20)


def test_roll_moves_unreleased_entries_under_the_version_and_updates_links() -> None:
    assert roll_changelog(BEFORE, "0.2.0", DAY) == AFTER


def test_release_notes_are_the_version_section() -> None:
    assert release_notes(AFTER, "0.2.0") == "### Added\n\n- Training load page.\n"
    assert release_notes(AFTER, "0.1.0") == "### Added\n\n- Parsers.\n"


def test_rolled_changelog_can_be_rolled_again_once_entries_are_added() -> None:
    with pytest.raises(ReleaseError, match="empty"):
        roll_changelog(AFTER, "0.3.0", DAY)
    more = AFTER.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- A bug.\n", 1)
    rolled = roll_changelog(more, "0.3.0", DAY)
    assert release_notes(rolled, "0.3.0") == "### Fixed\n\n- A bug.\n"
    assert "[0.3.0]: https://github.com/o/r/compare/v0.2.0...v0.3.0" in rolled


@pytest.mark.parametrize(
    ("changelog", "version", "message"),
    [
        (BEFORE, "0.1.0", "already has a section"),
        (BEFORE, "0.0.9", "not greater"),
        (BEFORE, "0.3.0rc1", "not a version"),
        (BEFORE.replace("## [Unreleased]", "## Next"), "0.2.0", "no ## \\[Unreleased\\]"),
        (BEFORE.replace("[Unreleased]: ", "[Next]: "), "0.2.0", "link"),
    ],
)
def test_roll_refuses(changelog: str, version: str, message: str) -> None:
    with pytest.raises(ReleaseError, match=message):
        roll_changelog(changelog, version, DAY)


def test_release_notes_refuse_an_undated_or_missing_version() -> None:
    with pytest.raises(ReleaseError, match="no date"):
        release_notes(BEFORE.replace("## [Unreleased]", "## [0.2.0]"), "0.2.0")
    with pytest.raises(ReleaseError, match="no section"):
        release_notes(AFTER, "0.3.0")


def test_bump_compares_numerically() -> None:
    check_bump("0.9.0", "0.10.0")
    with pytest.raises(ReleaseError):
        check_bump("0.10.0", "0.9.0")
