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
    assert "Usage" in out


def test_cli_help_flag_prints_usage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert "Usage" in capsys.readouterr().out


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
    assert exc.value.code == 1
    assert "Usage" in capsys.readouterr().out


def test_cli_unknown_command_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr("sys.argv", ["whitesnout", "bogus"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Unknown command" in out


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
