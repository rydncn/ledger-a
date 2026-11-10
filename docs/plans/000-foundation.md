# 000. Foundation

**Status:** done · **Satisfies:** none (the gates, proved by breaking) · **Depends on:** none

The slice before the first behaviour: the design, the draft Python pack, the gates in the agent's loop and in CI, the samples, and the trial's record files. Its "tests" are the gates themselves, each seen to fail once on a clean tree (rules 9 and 15).

## Tasks

### Task 1: A uv project with the tool chain under the release-age cutoff

- **Test:** `uv lock` under `exclude-newer` seven days back refuses a version published this week
- **Code:** `pyproject.toml`, `uv.lock`, the minimal `tally.cli` with `--version` and a usage error
- **Observed by:** the refusal of ruff 0.17.4 at the first lock, then `uv sync --locked --no-build` and the four checks passing

### Task 2: The hooks driven by a Python `checks.json`

- **Test:** an edit that breaks lint is reported straight after the edit; a stop with a failing check is sent back
- **Code:** `.claude/checks.json`, the playbook's hook scripts, `.claude/settings.json`
- **Observed by:** running each hook as Claude Code does, with a planted fault, and seeing exit 2 / `decision: block`

### Task 3: CI for Python with every gate from the checklist that applies

- **Test:** each job fails on a planted fault and passes on the clean tree
- **Code:** `.github/workflows/ci.yml`, `scripts/{mutation_changed,audit,check_lock}.py`, `scripts/rules.json`
- **Observed by:** the run on the pull request, and the runs on the proof branch, one planted fault per step, recorded in the pull request

### Task 4: The design and its decisions

- **Test:** none (a document); checked from the three directions the template lists
- **Code:** `docs/design.md`, `docs/decisions/0001` to `0008`
- **Observed by:** the fresh-context review of this slice reading it against the brief

### Task 5: The samples and the record files

- **Test:** `file samples/*` reports a BOM with CRLF, ISO-8859 text, ASCII text
- **Code:** `samples/`, `.gitattributes`, `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`, `docs/python-pack/`
- **Observed by:** the `file` output and the bytes

## Done when

- [ ] Every gate has been seen to fail once and the pull request records how
- [ ] The quick checks and the tests pass in CI, with the pull request out of draft
- [ ] The fresh-context review has run and its findings are fixed or ruled on
- [ ] `docs/handoff.md` says where slice 1 starts
