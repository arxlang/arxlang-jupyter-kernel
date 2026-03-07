from __future__ import annotations

import runpy
import sys
from importlib import import_module
from typing import Any

import pytest
from ipykernel.kernelapp import IPKernelApp

from arxlang_jupyter_kernel.kernel import ArxKernel


def test_main_launches_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_launch_instance(*, kernel_class: type[ArxKernel]) -> None:
        captured["kernel_class"] = kernel_class

    monkeypatch.setattr(IPKernelApp, "launch_instance", fake_launch_instance)

    main_module = import_module("arxlang_jupyter_kernel.__main__")
    main_module.main()

    assert captured["kernel_class"] is ArxKernel


def test_main_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_launch_instance(*, kernel_class: type[ArxKernel]) -> None:
        captured["kernel_class"] = kernel_class

    monkeypatch.setattr(IPKernelApp, "launch_instance", fake_launch_instance)
    sys.modules.pop("arxlang_jupyter_kernel.__main__", None)

    runpy.run_module("arxlang_jupyter_kernel.__main__", run_name="__main__")

    assert captured["kernel_class"] is ArxKernel
