# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.
from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_workspace_pysim() -> None:
    override = os.environ.get("YGGDRASIM_REPRO_PYSIM_ROOT")
    if override:
        sys.path.insert(0, override)
        return

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            pysim_root = parent / "pysim"
            if pysim_root.is_dir():
                sys.path.insert(0, str(pysim_root))
            return


_ensure_workspace_pysim()

from pySim.esim.saip.templates import FilesAtMF

# ETSI TS 102 221 §13.2 Table 13.1.
EXPECTED_ICCID_FID = 0x2FE2


def main() -> int:
    matches = [item for item in FilesAtMF.files if item.name == "EF.ICCID"]
    if len(matches) != 1:
        print(f"expected exactly one EF.ICCID row at MF, found {len(matches)}")
        return 2

    fid = matches[0].fid
    print(f"EF.ICCID fid={fid:04X}")
    if fid != EXPECTED_ICCID_FID:
        print(
            f"EF.ICCID is declared at {fid:04X}; "
            f"TS 102 221 §13.2 assigns {EXPECTED_ICCID_FID:04X}."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
