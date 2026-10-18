# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: pySim's PE-SecurityDomain needs ``keyList`` and writes an empty one.

TCA SAIP V3.4.1 section 8.6.1 declares ``keyList SEQUENCE (SIZE (1..MAX)) OF
KeyObject OPTIONAL``. The first case encodes an SD without keys through pySim
and reports whether the bytes carry an empty ``keyList``; the second encodes
an SD that omits the member straight through the compiled module and decodes
it with pySim.

    python repro_sd_optional_key_list.py                # the pySim on the path
    python repro_sd_optional_key_list.py --compensated  # with the YggdraSIM fix
"""

from __future__ import annotations

import sys
from pathlib import Path


def _blank_sd():
    from pySim.esim.saip import ProfileElementSD

    sd = ProfileElementSD()
    sd.decoded[sd.header_name] = {"mandated": None, "identification": 1}
    return sd


def _encode_without_keys() -> str:
    from pySim.esim.saip import asn1

    der = _blank_sd().to_der()
    _choice, body = asn1.decode("ProfileElement", der)
    if "keyList" not in body:
        return "keyList absent -> OK"
    return f"keyList present with {len(body['keyList'])} entries -> WRONG"


def _decode_without_key_list() -> str:
    from pySim.esim.saip import ProfileElement, asn1

    body = dict(_blank_sd().decoded)
    body.pop("keyList", None)
    der = asn1.encode("ProfileElement", ("securityDomain", body))
    try:
        element = ProfileElement.from_der(der)
    except KeyError as error:
        return f"KeyError {error} -> WRONG"
    keys = list(getattr(element, "keys", []))
    if "keyList" in element.decoded:
        return "decoded with keyList added -> WRONG"
    return f"decoded, {len(keys)} keys, keyList still absent -> OK"


def main() -> int:
    if "--compensated" in sys.argv[1:]:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from Tools.ProfilePackage.saip_pysim_compat import (
            install_optional_security_domain_key_list,
        )

        install_optional_security_domain_key_list()
    print("SD without keys, encoded:", _encode_without_keys())
    print("SD omitting keyList, decoded:", _decode_without_key_list())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
