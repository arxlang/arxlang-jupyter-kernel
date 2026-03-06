"""
title: Implement the ArxLang Jupyter kernel.
"""

from __future__ import annotations

import subprocess
import threading
from typing import Any

from ipykernel.kernelbase import Kernel

from .compile_run import (
    ArxCommandConfig,
    ArxCommandError,
    ArxCompileError,
    ArxRuntimeError,
    ExecutionResult,
    ProcessObserver,
    compile_and_run,
)
from .session import SessionSourceManager


class ArxKernel(Kernel, ProcessObserver):
    """
    title: Execute Arx cells by compiling and running native binaries.
    attributes:
      _session:
        type: SessionSourceManager
      _config:
        type: ArxCommandConfig
      _process_lock:
        type: threading.Lock
      _current_process:
        type: subprocess.Popen[str] | None
    """

    _session: SessionSourceManager
    _config: ArxCommandConfig
    _process_lock: threading.Lock
    _current_process: subprocess.Popen[str] | None

    implementation = "arxlang-jupyter-kernel"
    implementation_version = "0.1.0"
    language = "arx"
    language_version = "0.0.0"
    banner = "ArxLang Jupyter kernel"
    language_info = {
        "name": "arx",
        "version": "0.0.0",
        "mimetype": "text/x-arx",
        "file_extension": ".arx",
    }

    def __init__(self, **kwargs: Any) -> None:
        """
        title: Initialize kernel state.
        parameters:
          kwargs:
            type: Any
            variadic: keyword
        """
        super().__init__(**kwargs)
        self._session = SessionSourceManager.from_env()
        self._config = ArxCommandConfig.from_env()
        self._process_lock = threading.Lock()
        self._current_process: subprocess.Popen[str] | None = None

    def do_execute(
        self,
        code: Any,
        silent: Any,
        store_history: Any = True,
        user_expressions: Any = None,
        allow_stdin: Any = False,
        *,
        cell_meta: Any = None,
        cell_id: Any = None,
    ) -> dict[str, Any]:
        """
        title: Compile and execute one Arx cell.
        parameters:
          code:
            type: Any
          silent:
            type: Any
          store_history:
            type: Any
          user_expressions:
            type: Any
          allow_stdin:
            type: Any
          cell_meta:
            type: Any
          cell_id:
            type: Any
        returns:
          type: dict[str, Any]
        """
        _ = (allow_stdin, cell_meta, cell_id)
        code_text = code if isinstance(code, str) else str(code)
        silent_flag = bool(silent)
        store_history_flag = bool(store_history)

        if isinstance(user_expressions, dict):
            expressions = {
                str(key): value for key, value in user_expressions.items()
            }
        else:
            expressions = {}

        if not code_text.strip():
            return self._ok_reply(expressions)

        full_source = self._session.build_source(code_text)
        try:
            result = compile_and_run(
                full_source,
                config=self._config,
                observer=self,
            )
        except ArxCommandError as error:
            return self._error_reply(error, silent=silent_flag)

        self._emit_streams(result, silent=silent_flag)
        if store_history_flag:
            self._session.append_successful_cell(code_text)
        return self._ok_reply(expressions)

    def do_interrupt(self) -> dict[str, str]:
        """
        title: Terminate the active subprocess on kernel interrupt.
        returns:
          type: dict[str, str]
        """
        self._terminate_current_process()
        return {"status": "ok"}

    def set_process(self, process: subprocess.Popen[str]) -> None:
        """
        title: Track a subprocess so interrupts can terminate it.
        parameters:
          process:
            type: subprocess.Popen[str]
        """
        with self._process_lock:
            self._current_process = process

    def clear_process(self, process: subprocess.Popen[str]) -> None:
        """
        title: Clear tracked subprocess when it exits.
        parameters:
          process:
            type: subprocess.Popen[str]
        """
        with self._process_lock:
            if self._current_process is process:
                self._current_process = None

    def _emit_streams(self, result: ExecutionResult, *, silent: bool) -> None:
        """
        title: Publish compile and run output streams.
        parameters:
          result:
            type: ExecutionResult
          silent:
            type: bool
        """
        self._send_stream("stdout", result.compile_stdout, silent=silent)
        self._send_stream("stderr", result.compile_stderr, silent=silent)
        self._send_stream("stdout", result.run_stdout, silent=silent)
        self._send_stream("stderr", result.run_stderr, silent=silent)

    def _send_stream(self, name: str, text: str, *, silent: bool) -> None:
        """
        title: Send a Jupyter stream message when output is available.
        parameters:
          name:
            type: str
          text:
            type: str
          silent:
            type: bool
        """
        if silent or not text:
            return
        self.send_response(
            self.iopub_socket,
            "stream",
            {"name": name, "text": text},
        )

    def _ok_reply(self, expressions: dict[str, Any]) -> dict[str, Any]:
        """
        title: Build a successful execute reply payload.
        parameters:
          expressions:
            type: dict[str, Any]
        returns:
          type: dict[str, Any]
        """
        return {
            "status": "ok",
            "execution_count": self.execution_count,
            "payload": [],
            "user_expressions": expressions,
        }

    def _error_reply(
        self,
        error: ArxCommandError,
        *,
        silent: bool,
    ) -> dict[str, Any]:
        """
        title: Publish and return a failed execute reply payload.
        parameters:
          error:
            type: ArxCommandError
          silent:
            type: bool
        returns:
          type: dict[str, Any]
        """
        ename = self._error_name(error)
        details = error.stderr.strip() or error.stdout.strip() or str(error)
        detail_lines = [line for line in details.splitlines() if line.strip()]
        if not detail_lines:
            detail_lines = [str(error)]
        command_line = " ".join(error.command)
        traceback = [f"Command: {command_line}", *detail_lines]
        evalue = detail_lines[0]

        if not silent:
            self.send_response(
                self.iopub_socket,
                "error",
                {
                    "ename": ename,
                    "evalue": evalue,
                    "traceback": traceback,
                },
            )

        return {
            "status": "error",
            "execution_count": self.execution_count,
            "ename": ename,
            "evalue": evalue,
            "traceback": traceback,
        }

    def _error_name(self, error: ArxCommandError) -> str:
        """
        title: Map command errors to stable Jupyter ename values.
        parameters:
          error:
            type: ArxCommandError
        returns:
          type: str
        """
        if isinstance(error, ArxCompileError):
            return "ArxCompileError"
        if isinstance(error, ArxRuntimeError):
            return "ArxRuntimeError"
        return "ArxKernelError"

    def _terminate_current_process(self) -> None:
        """
        title: Terminate the tracked subprocess if it is running.
        """
        with self._process_lock:
            process = self._current_process

        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
