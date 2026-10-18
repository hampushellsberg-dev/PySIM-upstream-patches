# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: asn1tools decodes an OBJECT IDENTIFIER under arc 2 wrongly.

Encodes and decodes a few identifiers through a compiled DER module and
prints what comes back.

    python repro_oid_arc2.py                # the asn1tools on the path
    python repro_oid_arc2.py --compensated  # with the YggdraSIM fix
"""

from __future__ import annotations

import sys
from pathlib import Path

_OIDS = ("1.3.6.1.4.1.0", "2.23.143.1.2.1", "2.39.1", "2.40.1", "2.999.1", "2.25.1")


def main() -> int:
    if "--compensated" in sys.argv[1:]:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from yggdrasim_common.asn1tools_compat import install_object_identifier_arc2_decoding

        install_object_identifier_arc2_decoding()
    import asn1tools

    spec = asn1tools.compile_string("T DEFINITIONS ::= BEGIN O ::= OBJECT IDENTIFIER END", "der")
    for oid in _OIDS:
        der = spec.encode("O", oid)
        back = spec.decode("O", der)
        print(f"{oid:<16} {der.hex().upper():<16} -> {back:<16} {'OK' if back == oid else 'WRONG'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
