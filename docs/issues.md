# Issues, milestones and the roadmap board

How issues in `tanhtruong/makerundev` are labelled, scheduled and tracked on the [makerundev roadmap](https://github.com/users/tanhtruong/projects/7) board. Triage is done when every open issue passes the checklist below.

## Every open issue has

1. **One type label**: `enhancement`, `bug`, `documentation` or `tests` (tests only, no behaviour change). The issue templates set `bug` and `enhancement`.
2. **An area label** for each part it touches: `parsing`, `metrics`, `cli`, `app`, `sync`, `api`, `frontend`. A `documentation` issue needs one only when it documents a specific area.
3. **One contribution label**: `good first issue`, `help wanted` or `roadmap`, as CONTRIBUTING defines them.
4. **A milestone**, or the `roadmap` label and a pending decision (see Milestones).
5. **A Status on the board.** Priority and Size too, once it has a milestone.

## Milestones

A milestone is one release, named `<version> - <theme>` (`0.6.0 - CLI catch-up`) with a one-sentence description of what it ships.

- Give an issue the milestone of the release it should ship in.
- An issue stays unscheduled only while it waits on a decision: an ADR to merge (map view) or a model to choose (the metric roadmap). It carries `roadmap` and sits in Backlog; schedule it once the decision lands.
- Pull requests carry no milestone; the issue they close does.
- At `make publish` for `v<version>`: give closed issues from later milestones this milestone (they ship now), move this milestone's open issues to the next one, then close it.

A closed milestone is invisible to `gh issue edit --milestone`; set it by number instead: `gh api -X PATCH repos/tanhtruong/makerundev/issues/<n> -F milestone=<milestone number>`.

## The board

The board's built-in workflows auto-add items and sub-issues, set In review when a pull request is linked to an issue, and set Done when an item closes or merges. Check a new issue landed on the board, and set the other fields by hand:

| Status | Meaning |
| --- | --- |
| Backlog | Blocked, unscheduled, or not yet scoped. |
| Ready | Scoped, decided and unblocked. Contributors pick from here; `roadmap` items stay the maintainer's. |
| In progress | Someone has claimed it in a comment. |
| In review | A pull request that closes it is open. |
| Done | Closed. |

| Priority | Meaning |
| --- | --- |
| P0 | Other issues are blocked on it. |
| P1 | In the next milestone. |
| P2 | In a later milestone. |

| Size | Meaning |
| --- | --- |
| S | One area plus its tests; an afternoon. |
| M | Library and server, a migration, or a few days. |
| L | Needs an ADR or spans several pull requests. |

Set fields by name: `gh project item-edit 7 --owner tanhtruong --url <issue url> --field Status --value Ready`. Each call spends several GraphQL requests, and a few dozen in quick succession trip GitHub's secondary rate limit ("API rate limit already exceeded" while `gh api rate_limit` still shows quota). It clears after a few minutes; for bulk edits, one `updateProjectV2ItemFieldValue` mutation per item is cheaper.

## Dependencies

When an issue cannot start until another merges, record it as GitHub's blocked-by relation, say so in the first line of its body, and keep it in Backlog until the blocker closes:

```bash
gh api -X POST repos/tanhtruong/makerundev/issues/<blocked>/dependencies/blocked_by \
  -F issue_id="$(gh api repos/tanhtruong/makerundev/issues/<blocker> --jq .id)"
```

Work split into several issues under one parent uses sub-issues.
