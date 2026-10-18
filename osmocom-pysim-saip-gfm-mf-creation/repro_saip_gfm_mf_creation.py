# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.
"""Repro: a PE-GenericFileManagement that creates the MF fails to decode.

TCA "Profile interoperability technical specification" V3.4.1 §8.1 lets a
Full Profile create the MF with PE-GenericFileManagement instead of PE-MF,
and §7.5 forbids PE-MF in an IoT Minimal Profile. pySim's
``ProfileElementGFM.add_file`` dereferences ``pe_sequence.mf`` for every
file, so the createFCP that is the MF raises AttributeError.

Run from the YggdraSIM repository root with the project interpreter:

    python upstream_patches/osmocom-pysim-saip-gfm-mf-creation/repro_saip_gfm_mf_creation.py
    python upstream_patches/osmocom-pysim-saip-gfm-mf-creation/repro_saip_gfm_mf_creation.py --compensated

The first form runs upstream pySim as installed; the second installs the
YggdraSIM-side compensation (``install_gfm_mf_creation``) first.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from Tools.ProfilePackage.saip_json_codec import ensure_workspace_pysim_on_path  # noqa: E402

MF_FCP = {
    "fileDescriptor": b"\x78\x21",
    "fileID": b"\x3f\x00",
    "securityAttributesReferenced": b"\x01",
}
EF_ARR_FCP = {
    "fileDescriptor": b"\x42\x21\x00\x20",
    "fileID": b"\x2f\x06",
    "securityAttributesReferenced": b"\x03",
    "efFileSize": b"\x40",
}


def profile_der() -> bytes:
    from pySim.esim.saip import asn1

    header = asn1.encode("ProfileElement", ("header", {
        "major-version": 2,
        "minor-version": 3,
        "iccid": bytes.fromhex("988802214365870921F3"),
        "eUICC-Mandatory-services": {},
        "eUICC-Mandatory-GFSTEList": [],
    }))
    gfm = asn1.encode("ProfileElement", ("genericFileManagement", {
        "gfm-header": {"mandated": None, "identification": 1},
        "fileManagementCMD": [[
            ("createFCP", MF_FCP),
            ("createFCP", EF_ARR_FCP),
            ("fillFileContent", b"\x80\x01\x00\x90\x00"),
        ]],
    }))
    end = asn1.encode("ProfileElement", ("end", {
        "end-header": {"mandated": None, "identification": 2},
    }))
    return header + gfm + end


def main() -> int:
    compensated = "--compensated" in sys.argv[1:]
    if compensated:
        # ensure_workspace_pysim_on_path installs every YggdraSIM compensation.
        ensure_workspace_pysim_on_path(ROOT)
    else:
        import pySim  # noqa: F401  (the installed package, no compensation)

    from pySim.esim.saip import ProfileElementGFM, ProfileElementSequence

    add_file = ProfileElementGFM.add_file
    while getattr(add_file, "__wrapped__", None) is not None and not compensated:
        add_file = add_file.__wrapped__
    ProfileElementGFM.add_file = add_file

    print("mode:", "compensated" if compensated else "upstream")
    der = profile_der()
    print("profile:", len(der), "bytes; PE tags:", der[:1].hex(), "..", der[-9:-7].hex())
    try:
        pes = ProfileElementSequence.from_der(der)
    except Exception:  # noqa: BLE001 -- the repro reports whatever upstream raises
        print("FAIL")
        traceback.print_exc(limit=4)
        return 1
    gfm = pes.pe_list[1]
    print("OK types:", [pe.type for pe in pes.pe_list])
    print("sequence.mf:", pes.mf, "children:", sorted("%04X" % fid for fid in pes.mf.children))
    print("gfm.files:", sorted(gfm.files))
    print("round trip byte-identical:", pes.to_der() == der)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
