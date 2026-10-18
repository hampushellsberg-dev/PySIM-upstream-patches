# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Minimal repro: pySim decodes a terminated file as an operational one.

``LifeCycleStatusInteger._from_bytes`` tests the operational states before
the termination state and looks for the termination bits in b8 b7 instead of
b4 b3, so every life cycle status integer in the range '0C'..'0F' -- the
whole termination state of ETSI TS 102 221 V18.4.0 table 11.7b -- is reported
as an operational state. Encoding 'termination' and decoding the result back
does not round trip.

    python repro_lcsi_termination.py
"""

from __future__ import annotations

import sys

from pySim.ts_102_221 import LifeCycleStatusInteger

# ETSI TS 102 221 V18.4.0 clause 11.1.1.4.9 table 11.7b, every value the
# table defines. The states are named as pySim names them.
TABLE_11_7B: tuple[tuple[int, object], ...] = (
    (0x00, "no_information"),
    (0x01, "creation"),
    (0x03, "initialization"),
    (0x04, "operational_deactivated"),   # b3 = 1, b1 = 0
    (0x06, "operational_deactivated"),   # b2 is "-" in the table
    (0x05, "operational_activated"),     # b3 = 1, b1 = 1
    (0x07, "operational_activated"),
    (0x0C, "termination"),               # b4 b3 = 1 1, b2 b1 = "-"
    (0x0D, "termination"),
    (0x0E, "termination"),
    (0x0F, "termination"),
    (0x15, 0x15),                        # b5 set: proprietary, not a state
    (0x12, 0x12),                        # b5 set: proprietary, not a state
    (0x02, 0x02),                        # RFU: no name to give it
)


def decode(lcsi: int) -> object:
    element = LifeCycleStatusInteger()
    element.from_tlv(bytes([0x8A, 0x01, lcsi]))
    return element.decoded


def encode(name: str) -> bytes:
    element = LifeCycleStatusInteger()
    element.from_dict({"life_cycle_status_integer": name})
    return element.to_tlv()


def main() -> int:
    failures: list[str] = []

    print("decode, table 11.7b:")
    for lcsi, expected in TABLE_11_7B:
        got = decode(lcsi)
        verdict = "OK    "
        if got != expected:
            verdict = "WRONG "
            failures.append(f"{lcsi:02X}")
        print(f"  {verdict} '{lcsi:02X}' -> {got!r:26} expected {expected!r}")

    print("\nround trip of the termination state:")
    encoded = encode("termination")
    round_tripped = decode(encoded[-1])
    verdict = "OK    "
    if round_tripped != "termination":
        verdict = "WRONG "
        failures.append("round trip")
    print(
        f"  {verdict} 'termination' -> {encoded.hex()} -> {round_tripped!r}"
    )

    if failures:
        print(f"\nFAIL: {len(failures)} case(s) wrong: {', '.join(failures)}")
        return 1
    print("\nPASS: every value of table 11.7b decodes to its state.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
