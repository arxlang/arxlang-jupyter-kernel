"""Session source management for the Arx Jupyter kernel."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SessionSourceManager:
    """Manage successful cell source for one kernel session.

    Parameters
    ----------
    snapshot_path : Path | None, optional
        Optional file used to persist the concatenated successful source.
    """

    snapshot_path: Path | None = None
    _cells: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Load persisted source when a snapshot file is configured."""
        if self.snapshot_path is None:
            return
        self.snapshot_path = self.snapshot_path.expanduser()
        if not self.snapshot_path.exists():
            return

        persisted = self.snapshot_path.read_text(encoding="utf-8").strip()
        if persisted:
            self._cells = [persisted]

    @classmethod
    def from_env(cls) -> "SessionSourceManager":
        """Create a manager from environment configuration.

        Returns
        -------
        SessionSourceManager
            Manager configured from `ARX_KERNEL_SESSION_FILE`, if set.
        """
        raw_path = os.environ.get("ARX_KERNEL_SESSION_FILE", "").strip()
        snapshot_path = Path(raw_path) if raw_path else None
        return cls(snapshot_path=snapshot_path)

    @property
    def source(self) -> str:
        """Return concatenated source for all successful cells."""
        return "\n\n".join(self._cells)

    def build_source(self, new_cell: str) -> str:
        """Build a full source unit for compiling the next cell.

        Parameters
        ----------
        new_cell : str
            New cell contents to append to the session prelude.

        Returns
        -------
        str
            Full source sent to the compiler.

        Notes
        -----
        TODO: Add an explicit Arx entrypoint wrapper here if the language
        requires one for notebook execution semantics.
        """
        prelude = self.source.strip()
        cell = new_cell.strip()
        if prelude and cell:
            return f"{prelude}\n\n{cell}"
        if prelude:
            return prelude
        return cell

    def append_successful_cell(self, cell: str) -> None:
        """Append a successful cell to the session prelude.

        Parameters
        ----------
        cell : str
            Cell source that compiled and ran successfully.
        """
        normalized = cell.strip()
        if not normalized:
            return
        self._cells.append(normalized)
        self._persist()

    def reset(self) -> None:
        """Clear all persisted and in-memory session source."""
        self._cells.clear()
        self._persist()

    def _persist(self) -> None:
        """Persist the current prelude when snapshot_path is configured."""
        if self.snapshot_path is None:
            return
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        contents = self.source
        if contents:
            contents = f"{contents}\n"
        self.snapshot_path.write_text(contents, encoding="utf-8")
