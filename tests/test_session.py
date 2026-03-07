from __future__ import annotations

from pathlib import Path

import pytest

from arxlang_jupyter_kernel.session import SessionSourceManager


def test_from_env_without_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARX_KERNEL_SESSION_FILE", raising=False)

    session = SessionSourceManager.from_env()

    assert session.snapshot_path is None
    assert session.source == ""


def test_from_env_loads_existing_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "session.x"
    snapshot.write_text("let answer = 42\n", encoding="utf-8")
    monkeypatch.setenv("ARX_KERNEL_SESSION_FILE", str(snapshot))

    session = SessionSourceManager.from_env()

    assert session.snapshot_path == snapshot
    assert session.source == "let answer = 42"
    assert session.build_source("print(answer)") == (
        "let answer = 42\n\nprint(answer)"
    )
    assert session.build_source("   ") == "let answer = 42"


def test_snapshot_path_missing_file(tmp_path: Path) -> None:
    session = SessionSourceManager(snapshot_path=tmp_path / "missing.x")

    assert session.source == ""


def test_build_source_when_prelude_empty() -> None:
    session = SessionSourceManager()

    assert session.build_source("  new_value() ") == "new_value()"


def test_append_and_reset_persist(tmp_path: Path) -> None:
    snapshot = tmp_path / "nested" / "snapshot.x"
    session = SessionSourceManager(snapshot_path=snapshot)

    session.append_successful_cell("  first()  ")
    session.append_successful_cell("   ")

    assert session.source == "first()"
    assert snapshot.read_text(encoding="utf-8") == "first()\n"

    session.append_successful_cell("second()")

    assert session.source == "first()\n\nsecond()"
    assert snapshot.read_text(encoding="utf-8") == "first()\n\nsecond()\n"

    session.reset()

    assert session.source == ""
    assert snapshot.read_text(encoding="utf-8") == ""
