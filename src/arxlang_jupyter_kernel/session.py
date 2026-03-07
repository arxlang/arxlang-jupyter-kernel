"""
title: Manage persisted session source for the Arx Jupyter kernel.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SessionSourceManager:
    """
    title: Manage successful cell source for one kernel session.
    attributes:
      snapshot_path:
        type: Path | None
      _cells:
        type: list[str]
    """

    snapshot_path: Path | None = None
    _cells: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """
        title: Load persisted source when a snapshot file is configured.
        """
        if self.snapshot_path is None:
            return
        self.snapshot_path = self.snapshot_path.expanduser()
        if not self.snapshot_path.exists():
            return

        persisted = self.snapshot_path.read_text(encoding="utf-8").strip()
        if persisted:
            self._cells = [persisted]

    @classmethod
    def from_env(cls) -> SessionSourceManager:
        """
        title: Create a manager from environment configuration.
        returns:
          type: SessionSourceManager
        """
        raw_path = os.environ.get("ARX_KERNEL_SESSION_FILE", "").strip()
        snapshot_path = Path(raw_path) if raw_path else None
        return cls(snapshot_path=snapshot_path)

    @property
    def source(self) -> str:
        """
        title: Return concatenated source for all successful cells.
        returns:
          type: str
        """
        return "\n\n".join(self._cells)

    def build_source(self, new_cell: str) -> str:
        """
        title: Build the full source unit for the next cell.
        parameters:
          new_cell:
            type: str
        returns:
          type: str
        """
        prelude = self.source.strip()
        cell = new_cell.strip()
        if prelude and cell:
            return f"{prelude}\n\n{cell}"
        if prelude:
            return prelude
        return cell

    def append_successful_cell(self, cell: str) -> None:
        """
        title: Append a successful cell to the session prelude.
        parameters:
          cell:
            type: str
        """
        normalized = cell.strip()
        if not normalized:
            return
        self._cells.append(normalized)
        self._persist()

    def reset(self) -> None:
        """
        title: Clear all persisted and in-memory session source.
        """
        self._cells.clear()
        self._persist()

    def _persist(self) -> None:
        """
        title: Persist the current prelude when snapshot path is configured.
        """
        if self.snapshot_path is None:
            return
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        contents = self.source
        if contents:
            contents = f"{contents}\n"
        self.snapshot_path.write_text(contents, encoding="utf-8")
