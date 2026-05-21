from __future__ import annotations

from whitesnout.utils import guess_content_type


def test_guess_content_type_html() -> None:
    assert guess_content_type("/index.html") == "text/html; charset=utf-8"


def test_guess_content_type_css() -> None:
    assert guess_content_type("/style.css") == "text/css; charset=utf-8"


def test_guess_content_type_js() -> None:
    assert guess_content_type("/app.js") == "application/javascript; charset=utf-8"


def test_guess_content_type_png() -> None:
    assert guess_content_type("/image.png") == "image/png"


def test_guess_content_type_jpg() -> None:
    assert guess_content_type("/photo.jpg") == "image/jpeg"


def test_guess_content_type_svg() -> None:
    assert guess_content_type("/icon.svg") == "image/svg+xml"


def test_guess_content_type_woff2() -> None:
    assert guess_content_type("/font.woff2") == "font/woff2"


def test_guess_content_type_unknown() -> None:
    assert guess_content_type("/file.unknown") == "application/octet-stream"
