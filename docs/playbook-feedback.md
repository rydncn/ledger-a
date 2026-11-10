# Playbook feedback

Where the playbook (ai-playbook `dfc984a`) was wrong, slow, missing something, or assumed a web app or npm, recorded as it happened.

## Session 1 (slice 0)

- **The setup script for the cloud environment failed** before the session started: the container image ships an older uv earlier on `PATH` than the one the script installs, so `uv python install 3.15.2` ran against the old one. Nothing in `docs/agent-environment.md` says to call the installed binary by path or to check what `PATH` finds first. (Fixed in the environment; twenty minutes.)
- **No Python pack**, as the prompt said. Everything stack-specific had to be worked out: `templates/stacks/README.md`'s five steps were enough of a guide, but each took trial and error (release-age, source builds, mutation testing in-process). Draft pack in `docs/python-pack/`.
- **"Exact versions" and a release-age cutoff pull against each other.** `templates/npmrc` pins exact versions; with uv's `exclude-newer` an exact pin of this week's release cannot resolve. The lockfile is the exact pin in Python; the manifest holds ranges. Worth a line in `GATES.md`'s supply-chain item, which assumes npm.
- **`GATES.md`'s "install scripts off" has no per-package exception on Python** (`uv` has `--no-build` for all or none). `docs/new-project.md` already says a package that needs its install script gets an ADR; the pack notes how to do that with uv.
- **Mutation testing and acceptance tests through the real interface conflict in Python**: mutmut only sees in-process tests, so rule 16's "drive the real command line" and rule 15's mutation check can't both be satisfied by the same test. `GATES.md` says "on any other stack, prove it runs and kills a deliberate mutant", which is what caught it; the resolution (in-process `main(argv)` plus a few subprocess tests) is now in ADR 0002 and the pack.
- **The hooks' `pre-push` is npm-only** (it reads `package.json` scripts); the pack carries a shell version for uv. `templates/hooks/README.md` step 3 (`prepare` script) has no Python equivalent; the pack uses a `scripts/setup-dev.sh`.
- **`GATES.md`'s "the test run fails if no tests ran" needs no custom step for pytest** (exit 5), which the Go pack's "Tests ran" grep would suggest adding. Noted in the pack so nobody adds a redundant step.
- **CI ran every job in under 20 seconds**, which looked like it hadn't run at all; `GATES.md`'s "recent runs have been read" was the only reason the logs were read. Fine, but a note that a warm runner can be that quick would save a worry.
- **Record-keeping cost:** about a third of this session's wall clock went on `docs/` (effort, trial log, feedback, pack notes, ADRs, plan), as in both earlier trials.
