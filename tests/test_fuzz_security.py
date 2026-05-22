"""Property-based fuzz tests for the path sanitization invariants.

Invariant: ``sanitize_path(root, anything)`` either returns ``None`` or a
``Path`` that resolves *strictly inside* ``root``. There is no third option.
The Rust hot path and the Python fallback must both honor it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whitesnout.file_handler import sanitize_path

# Strategy: arbitrary URL-ish paths that an attacker could throw at the server.
# Covers traversal segments, encoded segments, control chars, nulls,
# Windows-style separators, mixed casing, long paths.
_path_strategy = st.recursive(
    st.one_of(
        st.text(
            alphabet=st.characters(
                min_codepoint=1,
                max_codepoint=0x10FFFF,
                blacklist_categories=("Cs",),  # exclude lone surrogates
            ),
            min_size=0,
            max_size=20,
        ),
        st.sampled_from(
            [
                "",
                ".",
                "..",
                "/",
                "//",
                "/..",
                "/.",
                "./",
                "../",
                "%2e%2e",
                "%2e%2e%2f",
                "%2E%2E%2F",
                "..%2f",
                "..%5c",
                "\\",
                "\\..\\",
                "C:\\Windows\\System32",
                "/etc/passwd",
                "\x00",
                "\r\n",
                "/foo\x00.txt",
                "/foo\r\nbar",
            ]
        ),
    ),
    lambda children: st.lists(children, min_size=1, max_size=5).map(
        lambda parts: "/" + "/".join(parts)
    ),
    max_leaves=10,
)


@given(_path_strategy)
@settings(max_examples=400, deadline=None)
def test_sanitize_never_escapes_root(
    tmp_path_factory: pytest.TempPathFactory, evil_path: str
) -> None:
    # Need a fresh root per call to keep the test deterministic with hypothesis
    root: Path = tmp_path_factory.mktemp("fuzz_root")
    (root / "ok.txt").write_text("safe")

    try:
        result = sanitize_path(str(root), evil_path)
    except (ValueError, OSError):
        # Some inputs (e.g. embedded nulls) legitimately raise — that's still
        # safe behavior. The invariant is "never returns an escaping path."
        return

    if result is None:
        return

    resolved = str(result)
    root_str = str(root.resolve())
    assert resolved.startswith(root_str + "/") or resolved == root_str, (
        f"Path escape: input={evil_path!r} -> {resolved!r}, root={root_str!r}"
    )


@given(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=100,
    )
)
@settings(max_examples=200, deadline=None)
def test_sanitize_no_leading_slash_never_escapes(
    tmp_path_factory: pytest.TempPathFactory, evil_path: str
) -> None:
    root: Path = tmp_path_factory.mktemp("fuzz_noslash")
    try:
        result = sanitize_path(str(root), evil_path)
    except (ValueError, OSError):
        return
    if result is None:
        return
    resolved = str(result)
    root_str = str(root.resolve())
    assert resolved.startswith(root_str + "/") or resolved == root_str
