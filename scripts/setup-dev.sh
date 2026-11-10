#!/bin/sh
# One-time development setup: the locked environment (wheels only) and git's
# hooks folder, which Python has no `prepare` script to set for us.
set -eu
cd "$(dirname "$0")/.."
uv sync --locked --no-build
git config core.hooksPath .claude/hooks
echo "ready: uv run tally --help"
