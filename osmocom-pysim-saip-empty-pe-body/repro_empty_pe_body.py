# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: a profile carrying an rfu PE does not load in pySim.

TCA SAIP V3.4.1 (page 16) keeps rfu1..rfu5 in the ProfileElement CHOICE as
``PE-Dummy ::= SEQUENCE {}``, a PE without members and without header. The
repro decodes one such PE on its own, then the TS.48 profile that ships with
pySim with the PE inserted before PE-End, and re-encodes both.

    PYTHONPATH=<pysim checkout> python repro_empty_pe_body.py

Exits 1 while either fails to load or does not re-encode to the same bytes, 0
once both do.
"""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    import pySim
    from pySim.esim.saip import ProfileElement, ProfileElementSequence, asn1, bertlv_first_segment

    print(f"pySim: {pySim.__file__}")
    rfu_der = asn1.encode("ProfileElement", ("rfu1", {}))
    failures = 0
    try:
        pe = ProfileElement.from_der(rfu_der)
        same = pe.to_der() == rfu_der
        print(f"rfu1 PE {rfu_der.hex()}: type {pe.type}, re-encodes {'the same' if same else 'differently'}")
        failures += 0 if same else 1
    except Exception as exc:
        print(f"rfu1 PE {rfu_der.hex()}: {type(exc).__name__}: {exc}")
        failures += 1

    upp = Path(pySim.__file__).resolve().parents[1] / "smdpp-data" / "upp" / "TS48v2_SAIP2.3_NoBERTLV.der"
    tlvs = []
    remainder = upp.read_bytes()
    while remainder:
        first, remainder = bertlv_first_segment(remainder)
        tlvs.append(first)
    der = b"".join(tlvs[:-1]) + rfu_der + tlvs[-1]
    try:
        pes = ProfileElementSequence.from_der(der)
        same = pes.to_der() == der
        print(f"TS.48 profile + rfu1 before PE-End: {len(pes.pe_list)} PEs, re-encodes "
              f"{'the same' if same else 'differently'}")
        failures += 0 if same else 1
    except Exception as exc:
        print(f"TS.48 profile + rfu1 before PE-End: {type(exc).__name__}: {exc}")
        failures += 1

    print("PASS" if not failures else f"FAIL: {failures} of 2 cases")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
