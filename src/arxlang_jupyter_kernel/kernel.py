"""Jupyter kernel implementation for ArxLang."""

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
    """A wrapper-style Jupyter kernel for Arx source execution."""

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
        """Initialize kernel state."""
        super().__init__(**kwargs)
        self._session = SessionSourceManager.from_env()
        self._config = ArxCommandConfig.from_env()
        self._process_lock = threading.Lock()
        self._current_process: subprocess.Popen[str] | None = None

    def do_execute(
        self,
        code: str,
        silent: bool,
        store_history: bool = True,
        user_expressions: dict[str, Any] | None = None,
        allow_stdin: bool = False,
    ) -> dict[str, Any]:
        """Compile and execute one Arx cell.

        Parameters
        ----------
        code : str
            User-provided cell code.
        silent : bool
            Whether execution should suppress output messages.
        store_history : bool, optional
            Whether this execution should be added to history/session state.
        user_expressions : dict[str, Any] | None, optional
            User expressions from the Jupyter protocol.
        allow_stdin : bool, optional
            Whether stdin is allowed. Unused by this kernel.

        Returns
        -------
        dict[str, Any]
            Jupyter execute reply payload.
        """
        _ = allow_stdin
        expressions = user_expressions or {}
        if not code.strip():
            return self._ok_reply(expressions)

        full_source = self._session.build_source(code)
        try:
            result = compile_and_run(
                full_source,
                config=self._config,
                observer=self,
            )
        except ArxCommandError as error:
            return self._error_reply(error, silent=silent)

        self._emit_streams(result, silent=silent)
        if store_history:
            self._session.append_successful_cell(code)
        return self._ok_reply(expressions)

    def do_interrupt(self) -> dict[str, str]:
        """Terminate the active subprocess on kernel interrupt.

        Returns
        -------
        dict[str, str]
            Jupyter interrupt reply payload.
        """
        self._terminate_current_process()
        return {"status": "ok"}

    def set_process(self, process: subprocess.Popen[str]) -> None:
        """Track a subprocess so interrupts can terminate it.

        Parameters
        ----------
        process : subprocess.Popen[str]
            Active subprocess to track.
        """
        with self._process_lock:
            self._current_process = process

    def clear_process(self, process: subprocess.Popen[str]) -> None:
        """Clear tracked subprocess when it exits.

        Parameters
        ----------
        process : subprocess.Popen[str]
            Completed subprocess.
        """
        with self._process_lock:
            if self._current_process is process:
                self._current_process = None

    def _emit_streams(self, result: ExecutionResult, *, silent: bool) -> None:
        """Publish compile/run streams to Jupyter clients.

        Parameters
        ----------
        result : ExecutionResult
            Compile and run outputs.
        silent : bool
            Whether stream output should be suppressed.
        """
        self._send_stream("stdout", result.compile_stdout, silent=silent)
        self._send_stream("stderr", result.compile_stderr, silent=silent)
        self._send_stream("stdout", result.run_stdout, silent=silent)
        self._send_stream("stderr", result.run_stderr, silent=silent)

    def _send_stream(self, name: str, text: str, *, silent: bool) -> None:
        """Send one stream message when output is available."""
        if silent or not text:
            return
        self.send_response(
            self.iopub_socket,
            "stream",
            {"name": name, "text": text},
        )

    def _ok_reply(self, expressions: dict[str, Any]) -> dict[str, Any]:
        """Build a successful execute reply payload."""
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
        """Publish and return a failed execute reply payload."""
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
        """Map command errors to stable Jupyter `ename` values."""
        if isinstance(error, ArxCompileError):
            return "ArxCompileError"
        if isinstance(error, ArxRuntimeError):
            return "ArxRuntimeError"
        return "ArxKernelError"

    def _terminate_current_process(self) -> None:
        """Terminate the tracked subprocess if it is still running."""
        with self._process_lock:
            process = self._current_process

        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
