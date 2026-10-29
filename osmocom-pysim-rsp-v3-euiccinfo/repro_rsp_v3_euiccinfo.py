# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Minimal repro: pySim's RSP module drops the SGP.22 v3 members of EUICCInfo1/2.

An SGP.22 v3.1 eUICC returns EUICCInfo1 with euiccCiPKIdListForSigningV3 [17],
euiccRspCapability [8] and highestSvn [19], and EUICCInfo2 with eight more
members [13]..[20] (SGP.22 v3.1 Annex H). The v2 module skips them without an
error, so osmo-smdpp's InitiateAuthentication never sees the v3 CI key list it
checks for. Exits 1 while any member is dropped, 0 once the patch is applied.

    python repro_rsp_v3_euiccinfo.py
"""

from __future__ import annotations

import sys

import pySim
import pySim.esim.rsp as rsp

SKI_V2 = "11" * 20
SKI_V3 = "22" * 20


def tlv(tag: str, value_hex: str) -> str:
    length = len(value_hex) // 2
    if length < 0x80:
        return tag + f"{length:02x}" + value_hex
    return tag + f"81{length:02x}" + value_hex


EUICC_INFO1_V3 = tlv(
    "bf20",
    tlv("82", "030100")
    + tlv("a9", tlv("04", SKI_V2))
    + tlv("aa", tlv("04", SKI_V2))
    + tlv("b1", tlv("04", SKI_V3))
    + tlv("88", "05900020")
    + tlv("93", "030100"),
)

EUICC_INFO2_V3 = tlv(
    "bf22",
    tlv("81", "030301")
    + tlv("82", "030100")
    + tlv("83", "010203")
    + tlv("84", "0103")
    + tlv("85", "0780")
    + tlv("88", "0490")
    + tlv("a9", tlv("04", SKI_V2))
    + tlv("aa", tlv("04", SKI_V2))
    + tlv("04", "010000")
    + tlv("0c", "")
    + tlv("8d", "0640")
    + tlv("8e", "544553542d545245")
    + tlv("af", tlv("04", "020300"))
    + tlv("90", "00")
    + tlv("b1", tlv("04", SKI_V3))
    + tlv("92", "cafe")
    + tlv("93", "030100")
    + tlv("b4", ""),
)

EXPECTED = {
    "EUICCInfo1": (EUICC_INFO1_V3, ("euiccCiPKIdListForSigningV3", "euiccRspCapability", "highestSvn")),
    "EUICCInfo2": (EUICC_INFO2_V3, (
        "treProperties", "treProductReference", "additionalProfilePackageVersions", "lpaMode",
        "euiccCiPKIdListForSigningV3", "additionalEuiccInfo", "highestSvn", "iotSpecificInfo",
    )),
}


def main() -> int:
    print(f"pySim from {pySim.__file__}\n")
    dropped: list[str] = []
    for type_name, (vector, members) in EXPECTED.items():
        data = bytes.fromhex(vector)
        decoded = rsp.asn1.decode(type_name, data)
        reencoded = rsp.asn1.encode(type_name, decoded)
        print(f"{type_name}: {len(data)} bytes in, {len(reencoded)} bytes re-encoded")
        for member in members:
            if member in decoded:
                print(f"  OK      {member}")
            else:
                print(f"  DROPPED {member}")
                dropped.append(f"{type_name}.{member}")
        print()
    if len(dropped) == 0:
        print("PASS: every SGP.22 v3 member of EUICCInfo1/2 decodes.")
        return 0
    print(f"FAIL: {len(dropped)} members dropped without an error: {', '.join(dropped)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
