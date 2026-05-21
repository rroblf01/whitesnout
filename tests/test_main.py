from __future__ import annotations

from whitesnout import WhiteSnout


def test_import() -> None:
    app = WhiteSnout()
    assert app is not None
    assert app.config.directory == "static"
