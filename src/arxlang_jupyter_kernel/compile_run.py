"""
title: Provide CLI helpers for compiling and running Arx source files.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProcessObserver(Protocol):
    """
    title: Define observer methods used to track active subprocesses.
    """

    def set_process(self, process: subprocess.Popen[str]) -> None:
        """
        title: Track a subprocess after it starts.
        parameters:
          process:
            type: subprocess.Popen[str]
        """
        ...

    def clear_process(self, process: subprocess.Popen[str]) -> None:
        """
        title: Clear a tracked subprocess after it exits.
        parameters:
          process:
            type: subprocess.Popen[str]
        """
        ...


@dataclass(frozen=True)
class ArxCommandConfig:
    """
    title: Store command configuration for Arx CLI integration.
    attributes:
      arx_bin:
        type: str
      compile_args:
        type: list[str]
      run_args:
        type: list[str]
      keep_build:
        type: bool
    """

    arx_bin: str
    compile_args: list[str]
    run_args: list[str]
    keep_build: bool

    @classmethod
    def from_env(cls) -> ArxCommandConfig:
        """
        title: Build command config from environment variables.
        returns:
          type: ArxCommandConfig
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
    """
    title: Store output from one subprocess invocation.
    attributes:
      returncode:
        type: int
      stdout:
        type: str
      stderr:
        type: str
    """

    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ExecutionResult:
    """
    title: Store outputs from successful compile and run stages.
    attributes:
      compile_stdout:
        type: str
      compile_stderr:
        type: str
      run_stdout:
        type: str
      run_stderr:
        type: str
    """

    compile_stdout: str
    compile_stderr: str
    run_stdout: str
    run_stderr: str


class ArxCommandError(RuntimeError):
    """
    title: Represent a failure from the Arx compile or run command.
    attributes:
      stage:
        type: str
      command:
        type: list[str]
      returncode:
        type: int
      stdout:
        type: str
      stderr:
        type: str
      build_dir:
        type: Path
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
    """
    title: Represent a compile stage failure.
    attributes:
      stage:
        type: str
      command:
        type: list[str]
      returncode:
        type: int
      stdout:
        type: str
      stderr:
        type: str
      build_dir:
        type: Path
    """


class ArxRuntimeError(ArxCommandError):
    """
    title: Represent a runtime stage failure.
    attributes:
      stage:
        type: str
      command:
        type: list[str]
      returncode:
        type: int
      stdout:
        type: str
      stderr:
        type: str
      build_dir:
        type: Path
    """


def build_compile_command(
    *,
    config: ArxCommandConfig,
    source_path: Path,
    binary_path: Path,
) -> list[str]:
    """
    title: Build the Arx compile command.
    parameters:
      config:
        type: ArxCommandConfig
      source_path:
        type: Path
      binary_path:
        type: Path
    returns:
      type: list[str]
    """
    command = [
        config.arx_bin,
        str(source_path),
        "--output-file",
        str(binary_path),
    ]
    command.extend(config.compile_args)
    return command


def build_run_command(
    *,
    config: ArxCommandConfig,
    binary_path: Path,
) -> list[str]:
    """
    title: Build the command used to run the compiled binary.
    parameters:
      config:
        type: ArxCommandConfig
      binary_path:
        type: Path
    returns:
      type: list[str]
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
    """
    title: Compile and run Arx source in a temporary build directory.
    parameters:
      source:
        type: str
      config:
        type: ArxCommandConfig | None
      observer:
        type: ProcessObserver | None
    returns:
      type: ExecutionResult
    """
    effective_config = config or ArxCommandConfig.from_env()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if effective_config.keep_build:
        build_dir = Path(tempfile.mkdtemp(prefix="arx-kernel-"))
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="arx-kernel-")
        build_dir = Path(temp_dir.name)

    try:
        source_path = build_dir / "main.x"
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
        run_result = _run_command(
            run_command, cwd=build_dir, observer=observer
        )
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
    """
    title: Run a subprocess command and capture its outputs.
    parameters:
      command:
        type: list[str]
      cwd:
        type: Path
      observer:
        type: ProcessObserver | None
    returns:
      type: CommandResult
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
    """
    title: Split shell-like argument strings into command tokens.
    parameters:
      raw_value:
        type: str
    returns:
      type: list[str]
    """
    if not raw_value.strip():
        return []
    return shlex.split(raw_value)


def _parse_bool(raw_value: str | None) -> bool:
    """
    title: Parse a boolean-like environment value.
    parameters:
      raw_value:
        type: str | None
    returns:
      type: bool
    """
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _binary_name() -> str:
    """
    title: Return a platform-specific executable filename.
    returns:
      type: str
    """
    return "main.exe" if os.name == "nt" else "main"
