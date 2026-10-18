# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Show which FID pySim's phonebook template resolves for a ranged file.

TCA SAIP v3.4.1 section 9.1: the first instance of a ranged file takes the
start value of the range. Exits non-zero on the first ``pe_name`` whose
``files_by_pename`` row is not the lowest FID listed for that name.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _put_pysim_on_path() -> None:
    override = os.environ.get("YGGDRASIM_REPRO_PYSIM_ROOT", "").strip()
    root = Path(override) if override else _REPO_ROOT / "pysim"
    if (root / "pySim" / "__init__.py").is_file():
        sys.path.insert(0, str(root))


def main() -> int:
    _put_pysim_on_path()
    if os.environ.get("YGGDRASIM_REPRO_SKIP_COMPAT", "") != "1":
        sys.path.insert(1, str(_REPO_ROOT))
        from Tools.ProfilePackage.saip_pysim_compat import (
            install_phonebook_pbc_template,
            install_template_range_start_fids,
        )

        install_phonebook_pbc_template()
        install_template_range_start_fids()
    from pySim.esim.saip.templates import FilesUsimDfPhonebook

    template = FilesUsimDfPhonebook
    lowest: dict[str, int] = {}
    for row in template.files:
        if row.fid is None:
            continue
        lowest[row.pe_name] = min(lowest.get(row.pe_name, row.fid), row.fid)
    failures = 0
    for pe_name in ("ef-adn", "ef-pbc", "ef-uid", "ef-ext1", "ef-ccp1", "ef-anr", "ef-grp"):
        row = template.files_by_pename.get(pe_name)
        if row is None:
            print(f"{pe_name:8} absent from files_by_pename")
            continue
        start = lowest.get(pe_name)
        verdict = "ok" if row.fid == start else "MISMATCH"
        if verdict != "ok":
            failures += 1
        print(f"{pe_name:8} resolves {row.fid:04X}  range start {start:04X}  {verdict}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
