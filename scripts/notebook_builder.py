"""Small helper for programmatically constructing + executing .ipynb notebooks.

Used by scripts/build_notebook_*.py. Cells are built from a plain list of (kind, source) tuples,
which keeps the notebook content readable/reviewable as Python rather than hand-written JSON.
Execution is real (nbclient against the registered `risk-engine` kernel) -- outputs embedded in
the saved .ipynb are actual computed results, not fabricated, per CLAUDE.md "No Fake Results".
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


def build_and_execute(cells: list[tuple[str, str]], output_path: Path, kernel_name: str = "risk-engine") -> None:
    nb = new_notebook()
    for kind, source in cells:
        if kind == "md":
            nb.cells.append(new_markdown_cell(source.strip()))
        elif kind == "code":
            nb.cells.append(new_code_cell(source.strip()))
        else:
            raise ValueError(f"unknown cell kind: {kind}")

    client = NotebookClient(nb, kernel_name=kernel_name, timeout=600)
    client.execute()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print(f"wrote executed notebook: {output_path}")
