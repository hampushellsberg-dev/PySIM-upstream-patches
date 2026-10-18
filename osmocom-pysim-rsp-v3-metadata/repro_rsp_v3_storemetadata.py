# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Minimal repro: pySim's RSP schema drops SGP.22 v3.1 metadata members.

Run against an unpatched pySim and every v3 member encodes to the same bytes
as omitting it -- no exception, no warning. Run against a patched one and each
member appears under the tag SGP.22 v3.1 §5.5.3 assigns it.

    python repro_rsp_v3_storemetadata.py
"""

from __future__ import annotations

import sys

from pySim.esim import compile_asn1_subdir

# (payload key, tag SGP.22 v3.1 §5.5.3 assigns, a minimal legal value)
V3_MEMBERS: tuple[tuple[str, str, object], ...] = (
    ("rpmConfiguration", "BA", {
        "managingDpList": [{"managingDpOid": "1.3.6.1.4.1.2"}],
        "profileOwnerOid": "1.3.6.1.4.1.3",
    }),
    ("hriServerAddress", "9B", "hri.example.test"),
    ("lprConfiguration", "BC", {"pcmpAddress": "pcmp.example.test"}),
    ("enterpriseConfiguration", "BD", {
        "enterpriseOid": "1.3.6.1.4.1.1",
        "enterpriseName": "Acme",
    }),
    ("serviceProviderMessage", "BE", {"message": "hello"}),
    ("serviceDescription", "9F1F", (b"\xC0", 2)),  # asn1tools: (payload, significant bits)
    ("deviceChangeConfiguration", "BF20",
     ("usingStoredAc", {"activationCodeForDc": "1$a$b"})),
    ("estimatedProfileSize", "9F21", 65536),
    ("serviceSpecificDataStoredInEuicc", "BF22",
     [{"vendorOid": "1.3.6.1.4.1.4", "vendorSpecificData": b"\x04\x02\xAA\xBB"}]),
    ("serviceSpecificDataNotStoredInEuicc", "BF23",
     [{"vendorOid": "1.3.6.1.4.1.5", "vendorSpecificData": b"\x04\x01\x00"}]),
)

BASE = {
    "iccid": bytes.fromhex("89882012345678901234"),
    "serviceProviderName": "SP",
    "profileName": "P",
}


def main() -> int:
    asn1 = compile_asn1_subdir("rsp")
    baseline = asn1.encode("StoreMetadataRequest", dict(BASE))
    print(f"baseline StoreMetadataRequest: {len(baseline)} bytes\n")

    dropped: list[str] = []
    for name, tag, value in V3_MEMBERS:
        try:
            encoded = asn1.encode("StoreMetadataRequest", dict(BASE, **{name: value}))
        except Exception as error:                      # noqa: BLE001 - repro
            print(f"  RAISED  {name:<36} {type(error).__name__}: {error}")
            dropped.append(name)
            continue
        if encoded == baseline:
            print(f"  DROPPED {name:<36} (expected tag {tag}) -- identical to baseline")
            dropped.append(name)
            continue
        present = tag in encoded.hex().upper()
        status = "OK     " if present else "NO TAG "
        print(f"  {status} {name:<36} tag {tag:<5} {len(baseline)} -> {len(encoded)} bytes")
        if not present:
            dropped.append(name)

    print()
    if len(dropped) == 0:
        print("PASS: every v3 member encodes under its assigned tag.")
        return 0
    print(f"FAIL: {len(dropped)} of {len(V3_MEMBERS)} members unreachable: "
          + ", ".join(dropped))
    return 1


if __name__ == "__main__":
    sys.exit(main())
