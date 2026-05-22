# Stability & Deprecation Policy

WhiteSnout follows [Semantic Versioning 2.0.0](https://semver.org/).

## Public API surface

Anything imported from these modules is **public** and covered by the version
contract below:

```python
from whitesnout import WhiteSnout, __version__
from whitesnout.django import get_static_application
from whitesnout.storage import (
    CompressedStaticFilesStorage,
    CompressedManifestStaticFilesStorage,
)
```

The `WhiteSnout.__init__` keyword arguments and the names exported from each
module's `__all__` are part of the API.

The following are **internal** and may change in any release without notice:

- The `whitesnout._rs` Rust extension module. Use the Python wrappers in
  `whitesnout.response`, `whitesnout.file_handler`, `whitesnout.cache`, and
  `whitesnout.utils` instead.
- Anything starting with `_` (private members).
- The shape of the `Config` dataclass (consumed only via `WhiteSnout(**kw)`).
- The wire format of internal caches (`_PyLRUCache`, `_PyStatCache`,
  `CompressedCache`).
- The exact set of headers WhiteSnout emits in error responses, beyond the
  HTTP status and the requirements documented in the README.

## What each version bump means

| Bump  | What can change                                                                 |
|-------|---------------------------------------------------------------------------------|
| Patch | Bug fixes, performance work, doc tweaks. No behavior change on the happy path.  |
| Minor | New keyword arguments with safe defaults, new modules, new optional extras.     |
| Major | Removal or rename of public API, change of a documented default, new minimum Python/Rust toolchain. |

A documented default counts as part of the contract — if the README says
"security headers are off by default," flipping that to on requires a major
bump.

## Python and toolchain support

- WhiteSnout supports the Python versions advertised in `pyproject.toml`
  classifiers and tested in CI (currently 3.10 – 3.14).
- Dropping a Python version is a **minor** bump if the version is already past
  its [upstream end-of-life](https://devguide.python.org/versions/), and a
  **major** bump otherwise.
- The Rust extension is built with the latest stable toolchain. The minimum
  supported Rust version is whatever ships with `rust-toolchain stable` at the
  time of release; we do not commit to a fixed MSRV.

## Deprecation process

When a public API needs to go away:

1. **Warn**: the next minor release adds a `DeprecationWarning` at import or
   first use, and the README/CHANGELOG calls out the replacement.
2. **Wait**: the deprecated API stays usable for at least **two minor
   releases** or **six months**, whichever is longer.
3. **Remove**: the next major release removes the API. The CHANGELOG entry
   under "Breaking" links back to the deprecation notice.

If a security issue forces an earlier removal, the release notes will say so
explicitly and a CVE will be issued per [SECURITY.md](SECURITY.md).

## Configuration defaults

Defaults are listed under "Configuration" in the README. We treat them as
load-bearing — flipping `security_headers=True` to `False`, changing the
default `chunk_size`, or altering the `immutable_pattern` regex is a major
bump.

Adding a **new** keyword argument with a backwards-compatible default is a
minor bump and does not require deprecation.

## ABI / wheel compatibility

- Wheels are built against the [Python stable ABI](https://docs.python.org/3/c-api/stable.html)
  (`abi3`) so a single wheel works across all supported Python versions on the
  same platform.
- The Rust extension does not expose a C ABI of its own — downstream Rust
  code should not depend on `whitesnout._rs` symbols.

## Out of scope for any version

These will **not** be added regardless of version:

- WSGI support (use Whitenoise — that is what it is for).
- HTTP/2 server push, HTTPS termination, request body upload handling.
- Authentication, authorization, rate limiting beyond what a reverse proxy
  already provides.

If you need one of those, WhiteSnout sits behind nginx, Caddy, Traefik, or a
CDN that already does it.
