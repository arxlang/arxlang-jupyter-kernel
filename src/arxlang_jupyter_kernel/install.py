"""
title: Install the ArxLang kernelspec into Jupyter.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any, cast

from jupyter_client.kernelspec import KernelSpecManager

KERNEL_ID = "arx"


def install_kernelspec(*, user: bool, prefix: str | None) -> Path:
    """
    title: Install the packaged kernelspec.
    parameters:
      user:
        type: bool
      prefix:
        type: str | None
    returns:
      type: Path
    """
    kernel_json = _load_kernel_json()
    argv = kernel_json.get("argv", [])
    if argv:
        argv[0] = sys.executable
        kernel_json["argv"] = argv

    with tempfile.TemporaryDirectory(prefix="arx-kernelspec-") as temp_dir:
        spec_dir = Path(temp_dir) / KERNEL_ID
        spec_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(kernel_json, indent=2, sort_keys=True)
        (spec_dir / "kernel.json").write_text(
            f"{payload}\n",
            encoding="utf-8",
        )

        manager = KernelSpecManager()
        destination = manager.install_kernel_spec(
            str(spec_dir),
            kernel_name=KERNEL_ID,
            user=user,
            prefix=prefix,
            replace=True,
        )

    return Path(destination)


def main(argv: list[str] | None = None) -> int:
    """
    title: Run the kernelspec installer CLI.
    parameters:
      argv:
        type: list[str] | None
    returns:
      type: int
    """
    parser = argparse.ArgumentParser(
        description="Install the ArxLang Jupyter kernelspec.",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        help="Install in the user kernelspec directory.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Install to a specific prefix path.",
    )
    args = parser.parse_args(argv)

    install_path = install_kernelspec(user=args.user, prefix=args.prefix)
    print(f"Installed kernelspec '{KERNEL_ID}' at: {install_path}")
    return 0


def _load_kernel_json() -> dict[str, Any]:
    """
    title: Load packaged kernelspec JSON data.
    returns:
      type: dict[str, Any]
    """
    resource = (
        resources.files("arxlang_jupyter_kernel")
        .joinpath("kernelspec")
        .joinpath("kernel.json")
    )
    with resources.as_file(resource) as kernel_json_path:
        text = kernel_json_path.read_text(encoding="utf-8")

    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Invalid kernelspec payload: root object must be map")
    return cast(dict[str, Any], payload)


if __name__ == "__main__":
    raise SystemExit(main())
