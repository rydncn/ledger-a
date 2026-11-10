# 7. Who merges, and on what evidence, without branch protection

**Status:** accepted · **Date:** 2026-11-10 · **Replaces:** none

## Context

Rule 9 wants CI as a required status check. This repository is private on a plan without branch protection, so nothing mechanical stops a merge on red. The trial's owner merges without reading the code, so the comparison measures the playbook.

## Decision

The agent opens every slice as a draft pull request, marks it ready when its plan's "done when" list holds, and asks the owner to merge. The owner merges only when every CI job on the pull request (Format, lint and types; Tests; Mutation testing on changed files; Dependencies and secrets) is green on the final commit and the pull request records the fresh-context review and its rulings. CI on `main` after each merge is the backstop. The ask rules on `git push` to `main` and on merging stay in `.claude/settings.json`.

## Rejected options

- **Merging on the agent's say-so:** the agent is the worst-placed judge of its own work.
- **Enabling branch protection:** not on this plan for a private repository; would be the first thing to do if it were.

## Consequences

Evidence is on the pull request page rather than enforced by GitHub, so each pull request's description says where it is.
