"""
title: Provide smoke tests for arxlang-jupyter-kernel.
"""

from __future__ import annotations

import json
from importlib import resources

from arxlang_jupyter_kernel.kernel import ArxKernel


def test_kernel_class_metadata() -> None:
    """
    title: Validate kernel language metadata.
    """
    assert ArxKernel.language == "arx"
    assert ArxKernel.language_info["file_extension"] == ".x"


def test_packaged_kernel_json() -> None:
    """
    title: Validate packaged kernelspec core fields.
    """
    kernel_json = (
        resources.files("arxlang_jupyter_kernel")
        .joinpath("kernelspec")
        .joinpath("kernel.json")
    )
    payload = json.loads(kernel_json.read_text(encoding="utf-8"))
    assert payload["display_name"] == "ArxLang"
    assert payload["language"] == "arx"
