"""Install the ArxLang kernelspec into Jupyter."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from jupyter_client.kernelspec import KernelSpecManager

KERNEL_ID = "arx"


def install_kernelspec(*, user: bool, prefix: str | None) -> Path:
    """Install the packaged kernelspec.

    Parameters
    ----------
    user : bool
        Install to the current user's Jupyter data directory.
    prefix : str | None
        Optional install prefix. Used for virtual-env style installs.

    Returns
    -------
    Path
        Installed kernelspec directory path.
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
    """CLI entrypoint for kernelspec installation.

    Parameters
    ----------
    argv : list[str] | None, optional
        CLI arguments. Defaults to `sys.argv[1:]`.

    Returns
    -------
    int
        Process exit code.
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
    """Load packaged kernelspec JSON data.

    Returns
    -------
    dict[str, Any]
        Parsed `kernel.json` content.
    """
    resource = resources.files("arxlang_jupyter_kernel").joinpath(
        "kernelspec",
        "kernel.json",
    )
    with resources.as_file(resource) as kernel_json_path:
        text = kernel_json_path.read_text(encoding="utf-8")
    return json.loads(text)


if __name__ == "__main__":
    raise SystemExit(main())
