"""Smoke tests for arxlang-jupyter-kernel package."""

from __future__ import annotations

import json
from importlib import resources

from arxlang_jupyter_kernel.kernel import ArxKernel


def test_kernel_class_metadata() -> None:
    """Kernel class exposes expected language metadata."""
    assert ArxKernel.language == "arx"
    assert ArxKernel.language_info["file_extension"] == ".arx"


def test_packaged_kernel_json() -> None:
    """Packaged kernelspec exists and has expected core fields."""
    kernel_json = resources.files("arxlang_jupyter_kernel").joinpath(
        "kernelspec",
        "kernel.json",
    )
    payload = json.loads(kernel_json.read_text(encoding="utf-8"))
    assert payload["display_name"] == "ArxLang"
    assert payload["language"] == "arx"
