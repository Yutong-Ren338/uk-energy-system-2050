"""
Insert a preamble code cell into a Jupyter notebook that:

- Ensures the output directory exists before saving figures
- Adds a default .png extension when missing
- Monkey-patches matplotlib.pyplot.savefig so existing calls keep working

Usage:
  python tools/inject_savefig_preamble.py nbs/Electricity\ Cost\ Final.ipynb --dir nbs/output
  python tools/inject_savefig_preamble.py nbs/Electricity\ Cost\ Final.ipynb --dir ../output
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PREAMBLE_MARK = "# <<SAFE_SAVEFIG_PRELUDE>>"


def build_preamble_code(output_dir: str) -> str:
    return f"""
{PREAMBLE_MARK}
from pathlib import Path
import matplotlib.pyplot as plt

OUT_DIR = Path(r"{output_dir}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

_orig_savefig = plt.savefig

def _safe_savefig(path, *args, **kwargs):
    p = Path(path)
    # Ensure .png extension if missing
    if p.suffix == "":
        p = p.with_suffix(".png")
    # Normalize common 'output/...' to OUT_DIR
    if not p.is_absolute():
        parts = p.parts
        if len(parts) > 0 and parts[0].lower() == "output":
            p = OUT_DIR.joinpath(*parts[1:])
        elif p.parent == Path("") or str(p.parent) == ".":
            # No directory specified, place under OUT_DIR
            p = OUT_DIR / p
    # Ensure directory exists
    p.parent.mkdir(parents=True, exist_ok=True)
    return _orig_savefig(p, *args, **kwargs)

plt.savefig = _safe_savefig
del _safe_savefig
""".strip()


def load_notebook(nb_path: Path) -> dict:
    data = json.loads(nb_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cells" not in data:
        raise ValueError("Not a valid .ipynb file")
    return data


def has_preamble(nb: dict) -> bool:
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            src = cell.get("source", [])
            text = "".join(src) if isinstance(src, list) else str(src)
            if PREAMBLE_MARK in text:
                return True
    return False


def replace_preamble(nb: dict, code: str) -> bool:
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            src = cell.get("source", [])
            text = "".join(src) if isinstance(src, list) else str(src)
            if PREAMBLE_MARK in text:
                cell["source"] = [line + "\n" for line in code.splitlines()]
                return True
    return False


def insert_preamble(nb: dict, code: str) -> None:
    cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in code.splitlines()],
    }
    nb["cells"] = [cell] + nb["cells"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path, help="Path to the .ipynb to modify")
    parser.add_argument(
        "--dir",
        dest="output_dir",
        default="output",
        help="Directory (relative to notebook CWD) to save figures",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh/replace existing preamble if found",
    )
    args = parser.parse_args()

    nb_path: Path = args.notebook
    nb = load_notebook(nb_path)

    if has_preamble(nb):
        if args.refresh:
            code = build_preamble_code(args.output_dir)
            if replace_preamble(nb, code):
                tmp_path = nb_path.with_suffix(".tmp.ipynb")
                tmp_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
                tmp_path.replace(nb_path)
                print(f"Preamble refreshed in {nb_path}")
                return
        print("Preamble already present; no changes made.")
        return

    code = build_preamble_code(args.output_dir)
    insert_preamble(nb, code)

    tmp_path = nb_path.with_suffix(".tmp.ipynb")
    tmp_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp_path.replace(nb_path)
    print(f"Inserted preamble into {nb_path}")


if __name__ == "__main__":
    main()
