from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from arxlang_jupyter_kernel import kernel as module
from arxlang_jupyter_kernel.compile_run import (
    ArxCommandConfig,
    ArxCommandError,
    ArxCompileError,
    ArxRuntimeError,
    ExecutionResult,
)
from arxlang_jupyter_kernel.kernel import ArxKernel


class FakeSession:
    def __init__(self, built_source: str) -> None:
        self.built_source = built_source
        self.built_calls: list[str] = []
        self.appended: list[str] = []

    def build_source(self, new_cell: str) -> str:
        self.built_calls.append(new_cell)
        return self.built_source

    def append_successful_cell(self, cell: str) -> None:
        self.appended.append(cell)


class StubProcess:
    def __init__(
        self, *, poll_result: int | None, timeout: bool = False
    ) -> None:
        self._poll_result = poll_result
        self._timeout = timeout
        self.terminated = False
        self.waited = False
        self.killed = False

    def poll(self) -> int | None:
        return self._poll_result

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        self.waited = True
        if self._timeout:
            raise subprocess.TimeoutExpired(cmd="arx", timeout=timeout)

    def kill(self) -> None:
        self.killed = True


def test_do_execute_empty_code(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ArxKernel()

    def fail_compile(*args: Any, **kwargs: Any) -> ExecutionResult:
        _ = (args, kwargs)
        raise AssertionError("compile_and_run should not be called")

    monkeypatch.setattr(module, "compile_and_run", fail_compile)

    reply = kernel.do_execute("  ", False, user_expressions={"x": 1})

    assert reply["status"] == "ok"
    assert reply["user_expressions"] == {"x": 1}


def test_do_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ArxKernel()
    session = FakeSession("full-source")
    kernel._session = cast(Any, session)
    kernel._config = ArxCommandConfig(
        arx_bin="arx",
        compile_args=[],
        run_args=[],
        keep_build=False,
    )

    seen: dict[str, Any] = {}

    def fake_compile(
        source: str,
        *,
        config: ArxCommandConfig | None = None,
        observer: Any = None,
    ) -> ExecutionResult:
        seen["source"] = source
        seen["config"] = config
        seen["observer"] = observer
        return ExecutionResult(
            compile_stdout="compile-out",
            compile_stderr="",
            run_stdout="",
            run_stderr="runtime-err",
        )

    streams: list[tuple[str, dict[str, Any]]] = []

    def capture_send(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        streams.append((args[1], args[2]))

    monkeypatch.setattr(module, "compile_and_run", fake_compile)
    monkeypatch.setattr(kernel, "send_response", capture_send)

    reply = kernel.do_execute("print(1)", False, user_expressions={"a": 1})

    assert reply["status"] == "ok"
    assert reply["user_expressions"] == {"a": 1}
    assert session.built_calls == ["print(1)"]
    assert session.appended == ["print(1)"]
    assert seen["source"] == "full-source"
    assert seen["config"] == kernel._config
    assert seen["observer"] is kernel
    assert streams == [
        ("stream", {"name": "stdout", "text": "compile-out"}),
        ("stream", {"name": "stderr", "text": "runtime-err"}),
    ]


def test_do_execute_silent_without_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = ArxKernel()
    session = FakeSession("full-source")
    kernel._session = cast(Any, session)

    def fake_compile(
        source: str,
        *,
        config: ArxCommandConfig | None = None,
        observer: Any = None,
    ) -> ExecutionResult:
        _ = (source, config, observer)
        return ExecutionResult(
            compile_stdout="compile-out",
            compile_stderr="compile-err",
            run_stdout="run-out",
            run_stderr="run-err",
        )

    events: list[tuple[Any, ...]] = []

    def capture_send(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        events.append(args)

    monkeypatch.setattr(module, "compile_and_run", fake_compile)
    monkeypatch.setattr(kernel, "send_response", capture_send)

    reply = kernel.do_execute(
        "print(2)",
        True,
        store_history=False,
        user_expressions=["invalid"],
    )

    assert reply["status"] == "ok"
    assert reply["user_expressions"] == {}
    assert session.appended == []
    assert events == []


def test_do_execute_compile_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    kernel = ArxKernel()
    session = FakeSession("full-source")
    kernel._session = cast(Any, session)

    error = ArxCompileError(
        stage="compile",
        command=["arx", "build", "main.arx"],
        returncode=1,
        stdout="",
        stderr="bad line\nother line",
        build_dir=tmp_path,
    )

    def fake_compile(
        source: str,
        *,
        config: ArxCommandConfig | None = None,
        observer: Any = None,
    ) -> ExecutionResult:
        _ = (source, config, observer)
        raise error

    events: list[tuple[str, dict[str, Any]]] = []

    def capture_send(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        events.append((args[1], args[2]))

    monkeypatch.setattr(module, "compile_and_run", fake_compile)
    monkeypatch.setattr(kernel, "send_response", capture_send)

    reply = kernel.do_execute("bad", False)

    assert reply["status"] == "error"
    assert reply["ename"] == "ArxCompileError"
    assert reply["evalue"] == "bad line"
    assert reply["traceback"] == [
        "Command: arx build main.arx",
        "bad line",
        "other line",
    ]
    assert session.appended == []
    assert events == [
        (
            "error",
            {
                "ename": "ArxCompileError",
                "evalue": "bad line",
                "traceback": [
                    "Command: arx build main.arx",
                    "bad line",
                    "other line",
                ],
            },
        )
    ]


def test_do_execute_runtime_error_silent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    kernel = ArxKernel()

    error = ArxRuntimeError(
        stage="run",
        command=["./main"],
        returncode=2,
        stdout="runtime failed",
        stderr="",
        build_dir=tmp_path,
    )

    def fake_compile(
        source: str,
        *,
        config: ArxCommandConfig | None = None,
        observer: Any = None,
    ) -> ExecutionResult:
        _ = (source, config, observer)
        raise error

    events: list[tuple[Any, ...]] = []

    def capture_send(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        events.append(args)

    monkeypatch.setattr(module, "compile_and_run", fake_compile)
    monkeypatch.setattr(kernel, "send_response", capture_send)

    reply = kernel.do_execute("bad", True)

    assert reply["status"] == "error"
    assert reply["ename"] == "ArxRuntimeError"
    assert reply["evalue"] == "runtime failed"
    assert events == []


def test_error_reply_fallback_message(tmp_path: Path) -> None:
    kernel = ArxKernel()
    error = ArxCommandError(
        stage="run",
        command=["arx", "run"],
        returncode=3,
        stdout="",
        stderr="",
        build_dir=tmp_path,
    )

    reply = kernel._error_reply(error, silent=True)

    assert reply["status"] == "error"
    assert reply["ename"] == "ArxKernelError"
    assert "Arx run command failed" in reply["evalue"]
    assert reply["traceback"][0] == "Command: arx run"


def test_error_name_for_error_types(tmp_path: Path) -> None:
    kernel = ArxKernel()
    compile_error = ArxCompileError(
        stage="compile",
        command=["arx", "build"],
        returncode=1,
        stdout="",
        stderr="",
        build_dir=tmp_path,
    )
    runtime_error = ArxRuntimeError(
        stage="run",
        command=["./main"],
        returncode=1,
        stdout="",
        stderr="",
        build_dir=tmp_path,
    )
    generic_error = ArxCommandError(
        stage="run",
        command=["arx", "run"],
        returncode=1,
        stdout="",
        stderr="",
        build_dir=tmp_path,
    )

    assert kernel._error_name(compile_error) == "ArxCompileError"
    assert kernel._error_name(runtime_error) == "ArxRuntimeError"
    assert kernel._error_name(generic_error) == "ArxKernelError"


def test_set_clear_and_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ArxKernel()
    first = cast(subprocess.Popen[str], object())
    second = cast(subprocess.Popen[str], object())

    kernel.set_process(first)
    kernel.clear_process(second)
    assert kernel._current_process is first

    kernel.clear_process(first)
    assert kernel._current_process is None

    called = {"value": False}

    def fake_terminate() -> None:
        called["value"] = True

    monkeypatch.setattr(kernel, "_terminate_current_process", fake_terminate)

    reply = kernel.do_interrupt()

    assert reply == {"status": "ok"}
    assert called["value"] is True


def test_terminate_current_process_branches() -> None:
    kernel = ArxKernel()

    kernel._current_process = None
    kernel._terminate_current_process()

    finished = StubProcess(poll_result=0)
    kernel._current_process = cast(Any, finished)
    kernel._terminate_current_process()
    assert finished.terminated is False

    running = StubProcess(poll_result=None)
    kernel._current_process = cast(Any, running)
    kernel._terminate_current_process()
    assert running.terminated is True
    assert running.waited is True
    assert running.killed is False

    hung = StubProcess(poll_result=None, timeout=True)
    kernel._current_process = cast(Any, hung)
    kernel._terminate_current_process()
    assert hung.terminated is True
    assert hung.waited is True
    assert hung.killed is True
