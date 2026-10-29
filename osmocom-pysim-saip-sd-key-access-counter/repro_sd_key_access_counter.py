# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: pySim drops keyAccess and keyCounterValue of a security domain key.

TCA SAIP V3.4.1 section 8.6.3 (page 56) defines ``KeyObject`` with
``keyAccess [22] OCTET STRING (SIZE (1)) DEFAULT '00'H`` and
``keyCounterValue [5] OCTET STRING OPTIONAL``. The repro takes the
PE-SecurityDomain of the TS.48 profile that ships with pySim, gives its first
key keyAccess '01' and a keyCounterValue, encodes that with pySim's compiled
module, then decodes and re-encodes it through ``ProfileElement``.

    PYTHONPATH=<pysim checkout> python repro_sd_key_access_counter.py

Exits 1 while the re-encode loses either field, 0 once it keeps both.
"""

from __future__ import annotations

import copy
from pathlib import Path


def main() -> int:
    import pySim
    from pySim.esim.saip import ProfileElement, ProfileElementSequence, asn1

    upp = Path(pySim.__file__).resolve().parents[1] / "smdpp-data" / "upp" / "TS48v2_SAIP2.3_NoBERTLV.der"
    pes = ProfileElementSequence.from_der(upp.read_bytes())
    decoded = copy.deepcopy(pes.get_pe_for_type("securityDomain").decoded)
    key = decoded["keyList"][0]
    key["keyAccess"] = b"\x01"
    key["keyCounterValue"] = b"\x00\x00\x01"
    der = asn1.encode("ProfileElement", ("securityDomain", decoded))
    again = ProfileElement.from_der(der).to_der()
    back = asn1.decode("ProfileElement", again)[1]["keyList"][0]
    print(f"pySim: {pySim.__file__}")
    print(f"in : keyAccess 01, keyCounterValue 000001, {len(der)} bytes")
    counter = back.get("keyCounterValue")
    print(f"out: keyAccess {back['keyAccess'].hex()}, keyCounterValue {counter.hex() if counter else 'absent'}, "
          f"{len(again)} bytes")
    if again == der:
        print("PASS: the re-encoded PE keeps both fields")
        return 0
    print("FAIL: the re-encoded PE lost keyAccess / keyCounterValue")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
