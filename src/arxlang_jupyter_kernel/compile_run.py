"""CLI helpers for compiling and running Arx source files."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProcessObserver(Protocol):
    """Observer interface for tracking active subprocesses."""

    def set_process(self, process: subprocess.Popen[str]) -> None:
        """Track a subprocess after it starts."""
        ...

    def clear_process(self, process: subprocess.Popen[str]) -> None:
        """Clear a tracked subprocess after it exits."""
        ...


@dataclass(frozen=True)
class ArxCommandConfig:
    """Command configuration for Arx CLI integration.

    Parameters
    ----------
    arx_bin : str
        Path or executable name for the Arx CLI.
    compile_args : list[str]
        Extra arguments appended to the compile command.
    run_args : list[str]
        Extra arguments appended to the run command.
    keep_build : bool
        Keep temporary build directories for debugging when true.
    """

    arx_bin: str
    compile_args: list[str]
    run_args: list[str]
    keep_build: bool

    @classmethod
    def from_env(cls) -> "ArxCommandConfig":
        """Build command config from environment variables.

        Returns
        -------
        ArxCommandConfig
            Configuration loaded from environment variables:
            `ARX_BIN`, `ARX_COMPILE_ARGS`, `ARX_RUN_ARGS`, and
            `ARX_KERNEL_KEEP_BUILD`.
        """
        arx_bin = os.environ.get("ARX_BIN", "arx")
        compile_args = _split_shell_like(
            os.environ.get("ARX_COMPILE_ARGS", "")
        )
        run_args = _split_shell_like(os.environ.get("ARX_RUN_ARGS", ""))
        keep_build = _parse_bool(os.environ.get("ARX_KERNEL_KEEP_BUILD"))
        return cls(
            arx_bin=arx_bin,
            compile_args=compile_args,
            run_args=run_args,
            keep_build=keep_build,
        )


@dataclass(frozen=True)
class CommandResult:
    """Result of executing a subprocess command."""

    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ExecutionResult:
    """Outputs gathered from successful compile and run stages."""

    compile_stdout: str
    compile_stderr: str
    run_stdout: str
    run_stderr: str


class ArxCommandError(RuntimeError):
    """Base exception for Arx compile/run command failures.

    Parameters
    ----------
    stage : str
        Stage name, usually `"compile"` or `"run"`.
    command : list[str]
        Full command that was executed.
    returncode : int
        Process exit code.
    stdout : str
        Captured standard output.
    stderr : str
        Captured standard error.
    build_dir : Path
        Build directory used for this execution.
    """

    stage: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    build_dir: Path

    def __init__(
        self,
        *,
        stage: str,
        command: list[str],
        returncode: int,
        stdout: str,
        stderr: str,
        build_dir: Path,
    ) -> None:
        self.stage = stage
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.build_dir = build_dir
        command_text = shlex.join(command)
        message = (
            f"Arx {stage} command failed with exit code {returncode}: "
            f"{command_text}"
        )
        super().__init__(message)


class ArxCompileError(ArxCommandError):
    """Compile-stage failure."""


class ArxRuntimeError(ArxCommandError):
    """Run-stage failure."""


def build_compile_command(
    *,
    config: ArxCommandConfig,
    source_path: Path,
    binary_path: Path,
) -> list[str]:
    """Build the Arx compile command.

    Parameters
    ----------
    config : ArxCommandConfig
        Active command configuration.
    source_path : Path
        Path to the generated source file.
    binary_path : Path
        Target path for the compiled executable.

    Returns
    -------
    list[str]
        Command tokens for subprocess execution.

    Notes
    -----
    TODO: Confirm the final Arx CLI contract. This default assumes:
    `arx build <source> -o <binary>`.
    """
    command = [
        config.arx_bin,
        "build",
        str(source_path),
        "-o",
        str(binary_path),
    ]
    command.extend(config.compile_args)
    return command


def build_run_command(
    *,
    config: ArxCommandConfig,
    binary_path: Path,
) -> list[str]:
    """Build the command used to run the compiled binary.

    Parameters
    ----------
    config : ArxCommandConfig
        Active command configuration.
    binary_path : Path
        Path to the compiled executable.

    Returns
    -------
    list[str]
        Command tokens for subprocess execution.
    """
    command = [str(binary_path)]
    command.extend(config.run_args)
    return command


def compile_and_run(
    source: str,
    *,
    config: ArxCommandConfig | None = None,
    observer: ProcessObserver | None = None,
) -> ExecutionResult:
    """Compile and run Arx source in a temporary build directory.

    Parameters
    ----------
    source : str
        Full Arx source to compile.
    config : ArxCommandConfig | None, optional
        Command configuration. If omitted, values are read from env vars.
    observer : ProcessObserver | None, optional
        Process observer used by the kernel for interrupt handling.

    Returns
    -------
    ExecutionResult
        Captured outputs from compile and run stages.

    Raises
    ------
    ArxCompileError
        Raised when the compile command exits non-zero.
    ArxRuntimeError
        Raised when the binary exits non-zero.
    """
    effective_config = config or ArxCommandConfig.from_env()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if effective_config.keep_build:
        build_dir = Path(tempfile.mkdtemp(prefix="arx-kernel-"))
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="arx-kernel-")
        build_dir = Path(temp_dir.name)

    try:
        source_path = build_dir / "main.arx"
        binary_path = build_dir / _binary_name()
        source_path.write_text(source, encoding="utf-8")

        compile_command = build_compile_command(
            config=effective_config,
            source_path=source_path,
            binary_path=binary_path,
        )
        compile_result = _run_command(
            compile_command,
            cwd=build_dir,
            observer=observer,
        )
        if compile_result.returncode != 0:
            raise ArxCompileError(
                stage="compile",
                command=compile_command,
                returncode=compile_result.returncode,
                stdout=compile_result.stdout,
                stderr=compile_result.stderr,
                build_dir=build_dir,
            )

        run_command = build_run_command(
            config=effective_config,
            binary_path=binary_path,
        )
        run_result = _run_command(run_command, cwd=build_dir, observer=observer)
        if run_result.returncode != 0:
            raise ArxRuntimeError(
                stage="run",
                command=run_command,
                returncode=run_result.returncode,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                build_dir=build_dir,
            )

        return ExecutionResult(
            compile_stdout=compile_result.stdout,
            compile_stderr=compile_result.stderr,
            run_stdout=run_result.stdout,
            run_stderr=run_result.stderr,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    observer: ProcessObserver | None = None,
) -> CommandResult:
    """Run a subprocess command and capture its outputs.

    Parameters
    ----------
    command : list[str]
        Command tokens to execute.
    cwd : Path
        Working directory for process execution.
    observer : ProcessObserver | None, optional
        Observer used for active process tracking.

    Returns
    -------
    CommandResult
        Captured return code, stdout, and stderr.
    """
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as error:
        return CommandResult(returncode=127, stdout="", stderr=str(error))

    if observer is not None:
        observer.set_process(process)
    try:
        stdout, stderr = process.communicate()
    finally:
        if observer is not None:
            observer.clear_process(process)

    returncode = process.returncode if process.returncode is not None else 1
    return CommandResult(returncode=returncode, stdout=stdout, stderr=stderr)


def _split_shell_like(raw_value: str) -> list[str]:
    """Split shell-like argument strings into command tokens.

    Parameters
    ----------
    raw_value : str
        Argument string from an environment variable.

    Returns
    -------
    list[str]
        Tokenized command arguments.
    """
    if not raw_value.strip():
        return []
    return shlex.split(raw_value)


def _parse_bool(raw_value: str | None) -> bool:
    """Parse a boolean-like environment value.

    Parameters
    ----------
    raw_value : str | None
        Input value from an environment variable.

    Returns
    -------
    bool
        True for common truthy values, otherwise False.
    """
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _binary_name() -> str:
    """Return a platform-specific executable filename."""
    return "main.exe" if os.name == "nt" else "main"
