# Contributing to WhiteSnout

Thanks for taking the time. WhiteSnout aims to be a small, fast, ASGI-only
static file server — contributions that fit that scope land quickly.

## Before you start

- Read [STABILITY.md](STABILITY.md) for the API contract and what counts as a
  breaking change.
- For security issues, follow [SECURITY.md](SECURITY.md) — do **not** open a
  public issue.
- Skim the [README](README.md) "Out of scope" / "Migration from Whitenoise"
  sections so you do not invest time on something we will decline (WSGI
  support, auth, rate limiting, HTTP/2 push).

## Dev setup

WhiteSnout is a hybrid Python + Rust project. Two ways to work on it:

### Native (recommended)

```console
$ uv sync --dev
$ uv run maturin develop --uv --release
$ uv run pytest
```

You need a stable Rust toolchain (`rustup default stable`) and Python 3.10+.

### Docker

```console
$ make build
$ make test
$ make shell    # interactive container
```

The Docker setup is what CI uses for parity. Native is faster locally.

## Before you push

```console
$ make check    # ruff + ty + cargo fmt + clippy
$ make test
```

All checks must pass. `cargo clippy` runs with `-D warnings` — new warnings
fail the build.

## Style

- Python: ruff + ruff format. The config in `pyproject.toml` is the source of
  truth. Do not add `# noqa` to silence unrelated lints; fix or refactor.
- Rust: `rustfmt` defaults. Keep PyO3 signatures simple — wrap complex
  marshalling in a Python adapter.
- No new comments unless the *why* is non-obvious. Function names are the
  documentation.

## What we will merge fast

- Bug fixes with a regression test.
- Performance improvements with a benchmark before/after.
- Doc improvements (especially examples and migration notes from Whitenoise).
- New optional integrations under `whitesnout.<framework>` that follow the
  pattern of `whitesnout.django`.

## What needs discussion first

Open an issue before sending a PR for:

- Anything that changes a default (security headers, immutable pattern,
  chunk size, etc.).
- New public keyword arguments on `WhiteSnout(...)`.
- New dependencies (Python or Rust).
- Breaking changes to `whitesnout.django`, `whitesnout.storage`, or
  `whitesnout.types`.

## Tests

- New features need tests in `tests/`. Look at `test_v2_features.py` and
  `test_edge_cases.py` for the patterns.
- Tests must run under `pytest -v` with no extra setup. Use `tmp_path` for
  filesystem fixtures; do not write to the repo.
- Security-relevant changes need a test in `tests/test_security.py`.
- For Rust changes, add a Python-level test that exercises the new behavior.
  We do not maintain Rust unit tests separately — the Python tests are the
  contract.

## Release process

Maintainers only:

1. Bump the version in `Cargo.toml`, `pyproject.toml`, and
   `src/whitesnout/__init__.py` (these must match).
2. Update `CHANGELOG.md` under a new heading. Mention any deprecations.
3. Commit, tag `vX.Y.Z`, push the tag.
4. The `publish` workflow builds wheels for all targets, runs the smoke
   test, and publishes via Trusted Publishing (OIDC).
5. Verify the release on PyPI and create a GitHub Release with the
   CHANGELOG section.

No long-lived PyPI tokens exist; only tagged commits from `main` can
publish.

## Code of Conduct

Be kind, be specific, assume good faith. Maintainers will remove comments or
contributors that make the project less pleasant to work on.
