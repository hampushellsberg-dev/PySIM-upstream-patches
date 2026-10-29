# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Minimal repro: a module importing OperatorId from pySim's RSPDefinitions fails to compile.

SGP.22 v3.1 Annex H (page 438) names the type OperatorId, and the SGP.32 v1.3
ASN.1 module imports it under that name: IMPORTS ... OperatorId ... FROM
RSPDefinitions. pySim's v2 module calls it OperatorID, so asn1tools refuses
the import. Exits 1 while it does, 0 once the patch adds the name.

    python repro_rsp_operatorid.py [path/to/SGP.32-v1.3.asn1]

With the optional path the published SGP.32 v1.3 module is compiled against
pySim's RSPDefinitions as well.
"""

from __future__ import annotations

import sys
from importlib import resources

import asn1tools
import pySim

IMPORTER = """Importer DEFINITIONS AUTOMATIC TAGS ::= BEGIN
IMPORTS OperatorId FROM RSPDefinitions {joint-iso-itu-t(2) international-organizations(23) gsma(146) rsp(1) asn1modules(1) sgp22v2(2)};
Owner ::= SEQUENCE { profileOwner [23] OperatorId }
END
"""


def rsp_text() -> str:
    directory = resources.files("pySim.esim").joinpath("asn1").joinpath("rsp")
    return "\n".join(entry.read_text(encoding="utf-8") for entry in directory.iterdir() if entry.name.endswith(".asn"))


def try_compile(label: str, text: str) -> bool:
    try:
        spec = asn1tools.compile_string(text, codec="der")
    except asn1tools.CompileError as error:
        print(f"  FAIL {label}: CompileError: {error}")
        return False
    print(f"  OK   {label}: modules {sorted(spec.modules)}")
    return True


def main() -> int:
    print(f"pySim from {pySim.__file__}")
    base = rsp_text()
    ok = try_compile("minimal importer of OperatorId", base + "\n" + IMPORTER)
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as handle:
            ok = try_compile("SGP.32 v1.3 module", base + "\n" + handle.read()) and ok
    print()
    if ok:
        print("PASS: OperatorId resolves in pySim's RSPDefinitions.")
        return 0
    print("FAIL: pySim's RSPDefinitions declares OperatorID, not OperatorId.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
