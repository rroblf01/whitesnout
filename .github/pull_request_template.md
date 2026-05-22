<!--
Thanks for the PR. Quick checklist before you submit:

- [ ] `make check` passes (ruff + ty + cargo fmt + clippy).
- [ ] `make test` passes locally.
- [ ] New behavior has a test under `tests/`.
- [ ] CHANGELOG.md updated under "Unreleased" if user-visible.
- [ ] No new public kwargs without discussion (see CONTRIBUTING.md).
- [ ] If this changes a default, the PR description says so explicitly.

For security fixes, see SECURITY.md — coordinate disclosure first.
-->

## Summary

<!-- 1–3 sentences. What changes, why. Link an issue if there is one. -->

## Behavior change

<!-- Yes/No. If yes, describe what users will see differently. -->

## Test plan

<!-- How did you verify? Include the exact `pytest -k ...` invocation if
relevant. For perf changes, include before/after numbers from
`benchmarks/benchmark.py`. -->

## Out of scope / follow-ups

<!-- Anything you intentionally left for another PR. -->
