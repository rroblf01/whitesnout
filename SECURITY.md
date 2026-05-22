# Security Policy

## Supported Versions

WhiteSnout follows [Semantic Versioning](https://semver.org/). Security fixes
target the latest minor release on the current major line. Older majors are
end-of-life unless explicitly stated below.

| Version | Status            | Security fixes |
|---------|-------------------|----------------|
| 2.x     | Active            | Yes            |
| 1.x     | End of life       | No             |

## Reporting a Vulnerability

**Do not open public GitHub issues for security problems.**

Report privately through one of:

- GitHub's [private vulnerability reporting](https://github.com/rrobles-qdq/whitesnout/security/advisories/new)
  (preferred — gives the maintainers a private workspace and coordinated
  disclosure timeline).
- Email the maintainer at `rrfernandez@qdqmedia.com` with subject
  `[whitesnout security]`.

Please include:

- A short description of the issue and its impact.
- Steps to reproduce or a proof of concept.
- Affected version(s) of WhiteSnout.
- Your suggested mitigation, if any.

## Response Timeline

| Stage                    | Target                |
|--------------------------|-----------------------|
| Initial acknowledgement  | Within 3 business days |
| Triage + severity rating | Within 7 business days |
| Fix or mitigation        | Depends on severity (see below) |
| Public disclosure        | Coordinated with reporter, typically after a patched release is on PyPI |

Severity guidance (CVSS v3.1 base score):

- **Critical (9.0 – 10.0)**: patch + release within 7 days.
- **High (7.0 – 8.9)**: patch + release within 14 days.
- **Medium (4.0 – 6.9)**: patch in next scheduled release (≤ 30 days).
- **Low (< 4.0)**: rolled into the next minor release.

## Scope

In scope:

- Path traversal, symlink escape, header injection, response smuggling, or any
  other way to read files outside the configured `directory`.
- Memory safety bugs in the Rust extension (`whitesnout._rs`).
- ASGI protocol violations that crash the host server or leak data across
  requests.
- Cache poisoning across the in-process compressed/stat caches.

Out of scope:

- Misconfigurations on the user's side (serving `directory="/"`, disabling
  security headers, etc.).
- Denial of service from absurd request volumes — WhiteSnout has no built-in
  rate limiting and is expected to sit behind a reverse proxy or load balancer
  for production traffic.
- Issues only reproducible with `_RUST_AVAILABLE = False` *and* an attacker
  who can also monkeypatch the running process.

## Supply Chain

- Releases are published to PyPI via GitHub Actions Trusted Publishing (OIDC).
  No long-lived PyPI tokens exist in repo or org secrets.
- Wheels are built in pinned GitHub-hosted runners using `cibuildwheel`.
- Dependabot tracks pip, cargo, and GitHub Actions versions.
- `cargo audit` and `pip-audit` run on every push to `main`.
