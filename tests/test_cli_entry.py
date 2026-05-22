"""Tests for the CLI entry point (`python -m whitesnout`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from whitesnout import cli


def test_cli_no_args_prints_usage_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage" in out.lower()


def test_cli_help_flag_prints_usage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_cli_short_help_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "-h"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0


def test_cli_compress_without_path_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "compress"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    # argparse exits 2 for missing positional, writes to stderr
    assert exc.value.code == 2
    assert "directory" in capsys.readouterr().err.lower()


def test_cli_unknown_command_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "bogus"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    # argparse rejects unknown subcommand with exit code 2
    assert exc.value.code == 2


def test_cli_compress_with_include_glob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / "app.css").write_text("body{}" * 50)
    (tmp_path / "skip.js").write_text("var x=1;" * 50)
    monkeypatch.setattr(
        "sys.argv",
        ["whitesnout", "compress", str(tmp_path), "--include", "*.css"],
    )
    cli.main()
    assert (tmp_path / "app.css.gz").is_file()
    assert not (tmp_path / "skip.js.gz").exists()


def test_cli_compress_with_exclude_glob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / "app.css").write_text("body{}" * 50)
    (tmp_path / "skip.css").write_text("body{}" * 50)
    monkeypatch.setattr(
        "sys.argv",
        ["whitesnout", "compress", str(tmp_path), "--exclude", "skip.*"],
    )
    cli.main()
    assert (tmp_path / "app.css.gz").is_file()
    assert not (tmp_path / "skip.css.gz").exists()


def test_cli_compress_quiet_suppresses_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / "app.css").write_text("body{}" * 50)
    monkeypatch.setattr(
        "sys.argv",
        ["whitesnout", "compress", str(tmp_path), "--quiet", "--jobs", "1"],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Compressed" not in out


def test_cli_compress_runs_on_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / "app.css").write_text("body { color: red; }\n" * 50)
    monkeypatch.setattr("sys.argv", ["whitesnout", "compress", str(tmp_path)])
    cli.main()  # no SystemExit on success
    out = capsys.readouterr().out
    assert "Compressed" in out
    assert (tmp_path / "app.css.gz").is_file()


def test_cli_compress_nonexistent_dir_prints_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "compress", "/no/such/dir"])
    cli.main()
    out = capsys.readouterr().out
    assert "Error" in out


# ---------- validate subcommand ----------


def test_cli_validate_existing_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / "a.css").write_text("x")
    monkeypatch.setattr("sys.argv", ["whitesnout", "validate", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "OK    directory" in out
    assert "OK    files: 1" in out


def test_cli_validate_missing_dir_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "validate", "/no/such/dir"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_validate_with_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"paths": {"app.css": "app.abc12345.css"}}',
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "whitesnout",
            "validate",
            str(tmp_path),
            "--manifest",
            str(manifest),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert "OK    manifest" in capsys.readouterr().out


def test_cli_validate_require_rust_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    # In dev environments where the rust ext is built (CI builds it explicitly)
    pytest.importorskip("whitesnout._rs")
    monkeypatch.setattr(
        "sys.argv",
        ["whitesnout", "validate", str(tmp_path), "--require-rust"],
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0


# ---------- serve subcommand (interface only — does not actually bind) ----------


def test_cli_serve_missing_dir_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pytest.importorskip("uvicorn")
    monkeypatch.setattr("sys.argv", ["whitesnout", "serve", "/no/such/dir"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert "not a directory" in capsys.readouterr().err


def test_cli_serve_invokes_uvicorn_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("uvicorn")
    import uvicorn

    captured: dict = {}

    def fake_run(app, **kwargs) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "whitesnout",
            "serve",
            str(tmp_path),
            "--port",
            "12345",
            "--health-check-path",
            "/healthz",
        ],
    )
    cli.main()
    from whitesnout import WhiteSnout

    assert isinstance(captured["app"], WhiteSnout)
    assert captured["kwargs"]["port"] == 12345
    assert captured["app"].config.health_check_path == "/healthz"
