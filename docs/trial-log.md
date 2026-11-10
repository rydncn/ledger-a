# Trial log

Per slice, the defects each layer found, one line each. Layers: tests, hooks, CI, gate breaks, the fresh-context review, the whole-codebase review, the audit. A "gate break" line records a gate that was broken on purpose and seen to fail, not a defect in the product.

## Slice 0: foundation

- Gate break, after-edit hook: a planted unused import in `src/tally/_planted.py` reported by `ruff check` straight after the edit, exit 2.
- Gate break, before-stop hook: a planted `return "x"` from an `-> int` function; `mypy` failed and the hook answered `decision: block`.
- Gate break, pre-push hook: the same type error; `git push --dry-run` refused with "nothing was pushed".
- Gate break, rule check: `float("1.10")` under `src/` failed `no-float-for-money`; pointed at a tree with no `src/`, the check failed with "no files to check" (exit 1).
- Gate break, lockfile integrity: a wheel URL moved to another host failed `check_lock.py`; a hash changed to `md5:` was refused by uv itself before the script ran.
- Gate break, stale lockfile: a dependency added to `pyproject.toml` without relocking failed `uv lock --check`.
- Gate break, dependency audit: an allowlist entry whose `expires` had passed failed `audit.py` before pip-audit ran.
- Gate break, empty test run: `pytest` on a directory with no tests exited 5.
- Gate break, mutation testing (not planted): the first real run on `cli.py` left 13 survivors in the parser's help text, then 1 (an `XX…XX` wrapping of the description a substring assertion let through), then 0 after the help test asserted whole lines.
- Gate break, release age: `exclude-newer` refused ruff 0.17.4 (published 2026-11-05) at the first lock, before any other gate existed.
- Gate break, CI (proof branch `proof/gate-breaks-1`, pull request #2, four runs): Format on `x=1`; Tests on a planted `assert 1 == 2`; Tests on an empty suite (pytest exit 5, "no tests ran"); Mutation on the help test removed (13 survivors reported, exit 1) and on a failing suite ("failed to collect stats"); Secrets scan on a random `ghp_` token (`github-pat`, 1 leak); Types on a planted `return "not an int"`; Lockfile integrity on a wheel URL moved to another host, before anything installed; Dependency audit on an expired allowlist entry; Rule checks on `float("1.10")` under `src/`; Lint on an unused import that the formatter accepted; Workflow security lint (zizmor) on a checkout without `persist-credentials: false` (artipacked). Every job has been seen red for its own reason; the branch and its token are deleted.
