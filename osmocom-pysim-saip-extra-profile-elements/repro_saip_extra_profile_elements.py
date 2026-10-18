#!/usr/bin/env python3
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.
"""Repro: pySim has no ProfileElement class for cdmaParameter, nonStandard, iot and opt-iot.

Builds the smallest IoT Minimal Profile (header, iot, opt-iot, end; TCA SAIP
V3.4.1 Section 7.5) with pySim's own ASN.1 module, then checks what pySim
makes of it. Only pySim is imported, so the script runs against any checkout:

    PYTHONPATH=/path/to/pysim python3 repro_saip_extra_profile_elements.py

Exit status 1 on stock pySim (the four types resolve to no class, the decoded
elements carry no files and the sequence has no MF), 0 with the patch applied.
"""

from __future__ import annotations

import sys

from pySim.esim.saip import ProfileElement, ProfileElementSequence, asn1
from pySim.utils import enc_iccid, enc_imsi, h2b

ICCID = "8988201234567890123"
IMSI = "001010000000001"
IOT_OID = "2.23.143.1.2.17"
OPT_IOT_OID = "2.23.143.1.2.18"
TYPES = ("cdmaParameter", "nonStandard", "iot", "opt-iot")


def profile_der() -> bytes:
    iccid_ef = h2b(enc_iccid(ICCID))
    imsi_ef = h2b(enc_imsi(IMSI))
    header = asn1.encode("ProfileElement", ("header", {
        "major-version": 2,
        "minor-version": 3,
        "profileType": "iot-minimal",
        "iccid": iccid_ef,
        "eUICC-Mandatory-services": {"usim": None},
        "eUICC-Mandatory-GFSTEList": [IOT_OID],
    }))
    iot = asn1.encode("ProfileElement", ("iot", {
        "iot-header": {"mandated": None, "identification": 2},
        "templateID": IOT_OID,
        "mf": [],
        "ef-iccid": [("fillFileContent", iccid_ef)],
        "ef-dir": [],
        "ef-arr": [],
        "adf-usim": [],
        "ef-imsi": [("fillFileContent", imsi_ef)],
        "ef-arr-usim": [],
        "ef-ust": [("fillFileContent", bytes.fromhex("000000000100"))],
        "ef-acc": [("fillFileContent", bytes.fromhex("0001"))],
        "ef-ecc": [],
    }))
    opt_iot = asn1.encode("ProfileElement", ("opt-iot", {
        "optiot-header": {"mandated": None, "identification": 3},
        "templateID": OPT_IOT_OID,
        "ef-fdn": [("fillFileContent", b"\xff" * 26)],
        "df-df-5gs": [],
        "ef-5gs3gpploci": [("fillFileContent", b"\xff" * 20)],
        "df-df-saip": [],
        "ef-suci-calc-info-usim": [("fillFileContent", bytes.fromhex("A000"))],
    }))
    end = asn1.encode("ProfileElement", ("end", {
        "end-header": {"mandated": None, "identification": 4},
    }))
    return header + iot + opt_iot + end


def main() -> int:
    failures = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print("%s %s%s" % ("ok  " if ok else "FAIL", label, (" -- " + detail) if detail else ""))
        if not ok:
            failures += 1

    for pe_type in TYPES:
        cls = ProfileElement.class_for_petype(pe_type)
        check("class_for_petype(%r)" % pe_type, cls is not None, "returns %r" % (cls.__name__ if cls else None))

    der = profile_der()
    pes = ProfileElementSequence.from_der(der)
    print("     decoded:", [(pe.type, pe.__class__.__name__) for pe in pes.pe_list])
    iot = pes.pe_list[1]
    opt_iot = pes.pe_list[2]
    check("PE-IoT carries File objects", bool(getattr(iot, "files", None)),
          "files=%s" % sorted(getattr(iot, "files", {}) or {}))
    check("sequence has an MF", pes.mf is not None)
    adf = None
    if pes.mf is not None:
        try:
            adf = pes.mf[0x7FF1]
        except KeyError:
            adf = None
    check("ADF.USIM 7FF1 below the MF", adf is not None)
    if adf is not None:
        check("EF.IMSI 6F07 below ADF.USIM", 0x6F07 in adf.children, "children=%s" % [hex(c) for c in adf.children])
        check("PE-IoT.imsi decodes", getattr(iot, "imsi", None) == IMSI, "imsi=%r" % getattr(iot, "imsi", None))
        df_5gs = adf.children.get(0x5FC0)
        df_saip = adf.children.get(0x5FD0)
        check("PE-OPT-IoT EF.FDN below ADF.USIM", 0x6F3B in adf.children)
        check("DF.5GS 5FC0 with EF.5GS3GPPLOCI", df_5gs is not None and 0x4F01 in df_5gs.children)
        check("DF.SAIP 5FD0 with EF.SUCI_Calc_Info", df_saip is not None and 0x4F01 in df_saip.children)
        check("PE-OPT-IoT files placed", len(getattr(opt_iot, "files", {}) or {}) >= 5,
              "files=%s" % sorted(getattr(opt_iot, "files", {}) or {}))
    grouped = {naa: [[pe.type for pe in group] for group in groups] for naa, groups in pes.pes_by_naa.items()}
    check("PE-IoT starts the usim NAA group", grouped == {"usim": [["iot", "opt-iot"]]}, "pes_by_naa=%s" % grouped)
    check("DER round trip is identical", pes.to_der() == der)
    print("result:", "PASS" if failures == 0 else "%d failure(s)" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
