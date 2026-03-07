from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from arxlang_jupyter_kernel import compile_run as module
from arxlang_jupyter_kernel.compile_run import (
    ArxCommandConfig,
    ArxCompileError,
    ArxRuntimeError,
    CommandResult,
    ExecutionResult,
    ProcessObserver,
    _binary_name,
    _parse_bool,
    _run_command,
    _split_shell_like,
    build_compile_command,
    build_run_command,
    compile_and_run,
)


class ObserverRecorder:
    def __init__(self) -> None:
        self.started: list[subprocess.Popen[str]] = []
        self.cleared: list[subprocess.Popen[str]] = []

    def set_process(self, process: subprocess.Popen[str]) -> None:
        self.started.append(process)

    def clear_process(self, process: subprocess.Popen[str]) -> None:
        self.cleared.append(process)


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARX_BIN", "my-arx")
    monkeypatch.setenv("ARX_COMPILE_ARGS", "--fast --target native")
    monkeypatch.setenv("ARX_RUN_ARGS", "--flag 'two words'")
    monkeypatch.setenv("ARX_KERNEL_KEEP_BUILD", "YES")

    config = ArxCommandConfig.from_env()

    assert config.arx_bin == "my-arx"
    assert config.compile_args == ["--fast", "--target", "native"]
    assert config.run_args == ["--flag", "two words"]
    assert config.keep_build is True


def test_build_commands() -> None:
    config = ArxCommandConfig(
        arx_bin="arx",
        compile_args=["--emit-ir"],
        run_args=["--verbose"],
        keep_build=False,
    )
    source_path = Path("/tmp/main.arx")
    binary_path = Path("/tmp/main")

    compile_command = build_compile_command(
        config=config,
        source_path=source_path,
        binary_path=binary_path,
    )
    run_command = build_run_command(config=config, binary_path=binary_path)

    assert compile_command == [
        "arx",
        "build",
        "/tmp/main.arx",
        "-o",
        "/tmp/main",
        "--emit-ir",
    ]
    assert run_command == ["/tmp/main", "--verbose"]


def test_compile_and_run_success_cleans_temp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "print(1)"
    calls: list[tuple[list[str], Path]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        observer: ProcessObserver | None = None,
    ) -> CommandResult:
        _ = observer
        calls.append((command, cwd))
        if len(calls) == 1:
            assert (cwd / "main.arx").read_text(encoding="utf-8") == source
            return CommandResult(returncode=0, stdout="cc-out", stderr="")
        return CommandResult(returncode=0, stdout="run-out", stderr="run-err")

    config = ArxCommandConfig(
        arx_bin="arx",
        compile_args=["--arg"],
        run_args=["--run-arg"],
        keep_build=False,
    )
    monkeypatch.setattr(module, "_run_command", fake_run)

    result = compile_and_run(source, config=config)

    assert result == ExecutionResult(
        compile_stdout="cc-out",
        compile_stderr="",
        run_stdout="run-out",
        run_stderr="run-err",
    )
    assert calls[0][0][0:2] == ["arx", "build"]
    assert calls[1][0][-1] == "--run-arg"
    assert calls[0][1].exists() is False


def test_compile_and_run_keep_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        observer: ProcessObserver | None = None,
    ) -> CommandResult:
        _ = (command, observer)
        calls.append(cwd)
        return CommandResult(returncode=0, stdout="ok", stderr="")

    config = ArxCommandConfig(
        arx_bin="arx",
        compile_args=[],
        run_args=[],
        keep_build=True,
    )
    monkeypatch.setattr(module, "_run_command", fake_run)

    compile_and_run("print(2)", config=config)

    build_dir = calls[0]
    assert build_dir.exists()
    shutil.rmtree(build_dir)


def test_compile_and_run_compile_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        observer: ProcessObserver | None = None,
    ) -> CommandResult:
        _ = (command, cwd, observer)
        return CommandResult(returncode=2, stdout="", stderr="bad compile")

    monkeypatch.setattr(module, "_run_command", fake_run)

    with pytest.raises(ArxCompileError) as raised:
        compile_and_run("bad")

    error = raised.value
    assert error.stage == "compile"
    assert "Arx compile command failed" in str(error)
    assert "bad compile" == error.stderr
    assert error.build_dir.exists() is False


def test_compile_and_run_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        observer: ProcessObserver | None = None,
    ) -> CommandResult:
        nonlocal call_count
        _ = (command, cwd, observer)
        call_count += 1
        if call_count == 1:
            return CommandResult(returncode=0, stdout="compiled", stderr="")
        return CommandResult(returncode=7, stdout="", stderr="bad run")

    monkeypatch.setattr(module, "_run_command", fake_run)

    with pytest.raises(ArxRuntimeError) as raised:
        compile_and_run("ok")

    error = raised.value
    assert error.stage == "run"
    assert "bad run" == error.stderr
    assert "Arx run command failed" in str(error)


def test_run_command_with_observer(tmp_path: Path) -> None:
    observer = ObserverRecorder()
    command = [
        sys.executable,
        "-c",
        (
            "import sys;"
            "print('stdout-text');"
            "print('stderr-text', file=sys.stderr)"
        ),
    ]

    result = _run_command(command, cwd=tmp_path, observer=observer)

    assert result.returncode == 0
    assert "stdout-text" in result.stdout
    assert "stderr-text" in result.stderr
    assert len(observer.started) == 1
    assert observer.started == observer.cleared


def test_run_command_oserror(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_popen(*args: Any, **kwargs: Any) -> subprocess.Popen[str]:
        _ = (args, kwargs)
        raise OSError("missing executable")

    monkeypatch.setattr(module.subprocess, "Popen", fail_popen)

    result = _run_command(["missing"], cwd=tmp_path)

    assert result.returncode == 127
    assert result.stdout == ""
    assert "missing executable" in result.stderr


def test_split_shell_like() -> None:
    assert _split_shell_like("") == []
    assert _split_shell_like("   ") == []
    assert _split_shell_like("--one 'two words'") == ["--one", "two words"]


def test_parse_bool() -> None:
    assert _parse_bool(None) is False
    assert _parse_bool("1") is True
    assert _parse_bool("YES") is True
    assert _parse_bool("off") is False


def test_binary_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module.os, "name", "nt", raising=False)
    assert _binary_name() == "main.exe"

    monkeypatch.setattr(module.os, "name", "posix", raising=False)
    assert _binary_name() == "main"
