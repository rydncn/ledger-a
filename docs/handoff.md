# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slice 0 (foundation)** is in pull request [#1](https://github.com/rydncn/ledger-a/pull/1), branch `claude/new-session-xwzj72`, awaiting the owner's merge. Everything a slice needs is in place: `docs/design.md` (AC1 to AC41, lifecycles, the slice table), ADRs 0001 to 0008, `CLAUDE.md`, the hooks, CI, the draft Python pack in `docs/python-pack/`, and the samples.
- **Next: slice 1**, accounts and the data file. Criteria AC1 to AC8, plus AC34 and AC35 for the commands it adds (`account add`, `account list`, `account forget`). Read `docs/design.md` § Shape and § Lifecycles, and ADRs 0004 (money), 0005 (locking), 0006 (configuration) before planning.

## How a slice goes

1. New session, new branch from `main` (`slice-1-accounts`), `scripts/setup-dev.sh`.
2. Plan in `docs/plans/001-accounts.md` from `docs/plans/000-foundation.md`'s shape: `### Task N:` headings, each with the failing test first, and the criteria it satisfies. Open the draft pull request straight away with the plan in the description and the door kind.
3. Test-first per task: `tests/test_acNN_*.py` names its criterion; in-process `main(argv)` for behaviour, one subprocess test per behaviour group (ADR 0002). The stop hook runs format, lint, mypy and the tests.
4. Before marking ready: `uv run python scripts/mutation_changed.py origin/main` (needs `UV_NO_BUILD=0 uv sync --locked --group mutation`), the fresh-context review from `docs/review-brief.md` by a subagent given only the diff, `CLAUDE.md` and `docs/design.md`, findings fixed test-first or ruled on in the pull request.
5. Records: `docs/effort.md` (one row per slice: sessions, peak context per session, wall clock), `docs/trial-log.md` (defects per layer, one line each), `docs/playbook-feedback.md`. Peak context: the hook's measure from the transcript; the script in `docs/python-pack/README.md` § "Measuring a session" reproduces it.
6. Handoff here, push, ask the owner to merge (ADR 0007).

## Decisions taken that the next session should not reopen

- Exit codes 0/1/2/3 and the stdout/stderr contract are in `docs/design.md` § Shape.
- The fingerprint for duplicates is ADR 0008; the amount sign convention (money in minus money out; a negative money-out is money back) is in § Shape.
- Subprocess tests kill no mutants (ADR 0002); don't move behaviour tests to subprocess to "be more real".

## Open

- Whether `account forget` should keep a tombstone so a later import of the same file into a re-created account is not silently "all new": decided no for slice 1 (the brief says delete everything); revisit if the reviewer raises it.
- After slice 3: the whole-codebase review. Before the final review: `/security-audit`.
