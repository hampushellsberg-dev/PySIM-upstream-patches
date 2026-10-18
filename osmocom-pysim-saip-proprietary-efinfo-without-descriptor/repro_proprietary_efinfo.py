# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: pySim ignores a template file's ``proprietaryEFInfo`` without ``fileDescriptor``.

Each case builds a pySim ``File`` from a TCA template file and an Fcp that
overrides only ``proprietaryEFInfo`` -- the shape TCA SAIP V3.4.1 section
8.3.3 allows for changing a template file's settings -- and prints the pattern
pySim read and the body it linearised.

    python repro_proprietary_efinfo.py                # the pySim on the path
    python repro_proprietary_efinfo.py --compensated  # with the YggdraSIM fix
"""

from __future__ import annotations

import sys
from pathlib import Path


def _cases() -> list[tuple[str, object, dict, bytes]]:
    from pySim.esim.saip import templates

    umpc = templates.FilesAtMF.files_by_pename["ef-umpc"]
    pl = templates.FilesAtMF.files_by_pename["ef-pl"]
    pnn = templates.FilesUsimOptional.files_by_pename["ef-pnn"]
    return [
        # Transparent, 5 B, no template default.
        ("EF.UMPC fillPattern '01FF'", umpc, {"fillPattern": b"\x01\xff"}, bytes.fromhex("01FFFFFFFF")),
        # Transparent, 2 B, template default 'FF...FF'.
        ("EF.PL fillPattern 'AA'", pl, {"fillPattern": b"\xaa"}, bytes.fromhex("AAAA")),
        # Linear fixed, 10 records of 16 B, no template default.
        ("EF.PNN fillPattern '00FF'", pnn, {"fillPattern": b"\x00\xff"}, (b"\x00" + b"\xff" * 15) * 10),
    ]


def main() -> int:
    if "--compensated" in sys.argv[1:]:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from Tools.ProfilePackage.saip_pysim_compat import (
            install_erased_state_file_fill,
            install_proprietary_efinfo_without_descriptor,
            install_record_aware_fill_pattern,
        )

        install_erased_state_file_fill()
        install_record_aware_fill_pattern()
        install_proprietary_efinfo_without_descriptor()
    from pySim.esim.saip import File

    failures = 0
    for label, template_file, pefi, expected in _cases():
        pe_file = File("repro", [("fileDescriptor", {"proprietaryEFInfo": dict(pefi)})], template_file)
        pattern = pe_file.fill_pattern.hex().upper() if pe_file.fill_pattern else "None"
        body = (pe_file.body or b"").hex().upper()
        ok = pe_file.body == expected
        failures += 0 if ok else 1
        shown = body if len(body) <= 40 else body[:40] + "..."
        print(f"{label}: fill_pattern={pattern} body={shown or '(empty)'} -> {'OK' if ok else 'WRONG'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
