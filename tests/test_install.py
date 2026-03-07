from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from arxlang_jupyter_kernel import install as module


class FakeKernelSpecManager:
    last_call: dict[str, Any] | None = None
    kernel_payload: dict[str, Any] | None = None

    def install_kernel_spec(
        self,
        source_dir: str,
        *,
        kernel_name: str,
        user: bool,
        prefix: str | None,
        replace: bool,
    ) -> str:
        payload = json.loads(
            (Path(source_dir) / "kernel.json").read_text(encoding="utf-8")
        )
        type(self).kernel_payload = payload
        type(self).last_call = {
            "source_dir": source_dir,
            "kernel_name": kernel_name,
            "user": user,
            "prefix": prefix,
            "replace": replace,
        }
        return str(Path(source_dir).parent / "installed" / kernel_name)


def test_load_kernel_json() -> None:
    payload = module._load_kernel_json()

    assert payload["display_name"] == "ArxLang"
    assert payload["language"] == "arx"


def test_load_kernel_json_invalid_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module.json, "loads", lambda _: [])

    with pytest.raises(ValueError, match="root object must be map"):
        module._load_kernel_json()


def test_install_kernelspec_updates_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_payload = {
        "argv": ["python", "-m", "arxlang_jupyter_kernel"],
        "display_name": "ArxLang",
        "language": "arx",
    }
    monkeypatch.setattr(module, "_load_kernel_json", lambda: fake_payload)
    monkeypatch.setattr(module, "KernelSpecManager", FakeKernelSpecManager)

    destination = module.install_kernelspec(user=True, prefix="/prefix")

    assert destination.name == module.KERNEL_ID
    assert FakeKernelSpecManager.last_call is not None
    assert FakeKernelSpecManager.last_call["kernel_name"] == module.KERNEL_ID
    assert FakeKernelSpecManager.last_call["user"] is True
    assert FakeKernelSpecManager.last_call["prefix"] == "/prefix"
    assert FakeKernelSpecManager.last_call["replace"] is True
    assert FakeKernelSpecManager.kernel_payload is not None
    assert FakeKernelSpecManager.kernel_payload["argv"][0] == sys.executable


def test_install_kernelspec_without_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_payload = {"display_name": "ArxLang", "language": "arx"}
    monkeypatch.setattr(module, "_load_kernel_json", lambda: fake_payload)
    monkeypatch.setattr(module, "KernelSpecManager", FakeKernelSpecManager)

    destination = module.install_kernelspec(user=False, prefix=None)

    assert destination.name == module.KERNEL_ID
    assert FakeKernelSpecManager.kernel_payload == fake_payload


def test_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    def fake_install(*, user: bool, prefix: str | None) -> Path:
        captured["user"] = user
        captured["prefix"] = prefix
        return Path("/tmp/arx/kernelspec")

    monkeypatch.setattr(module, "install_kernelspec", fake_install)

    status = module.main(["--user", "--prefix", "/tmp/prefix"])

    output = capsys.readouterr().out
    assert status == 0
    assert captured == {"user": True, "prefix": "/tmp/prefix"}
    assert "Installed kernelspec 'arx' at:" in output
