# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: pySim's optimised body encoding does not rebuild the body on the card.

Each case sets a ``File`` body, encodes it with
``file_content_to_tuples(optimize=True)`` and replays the tuples the way TCA
SAIP V3.4.1 section 8.3.5 defines them -- ``fillFileOffset`` moves the pointer
from where it stands, ``fillFileContent`` writes there and moves it past what
it wrote -- onto the content the eUICC creates the file with (section 8.3.3:
the Fcp pattern when there is one, otherwise the template default).

    python repro_optimised_body_encoding.py                # the pySim on the path
    python repro_optimised_body_encoding.py --compensated  # with the YggdraSIM fix
"""

from __future__ import annotations

import sys
from pathlib import Path


def _replay(base: bytes, tuples: list) -> bytes:
    image = bytearray(base)
    cursor = 0
    for key, value in tuples:
        if key == "fillFileOffset":
            cursor += int(value)
        elif key == "fillFileContent":
            if cursor > len(image):
                image += b"\xff" * (cursor - len(image))
            image[cursor:cursor + len(value)] = value
            cursor += len(value)
    return bytes(image)


def main() -> int:
    if "--compensated" in sys.argv[1:]:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from Tools.ProfilePackage.saip_pysim_compat import (
            install_body_encoding_against_creation_content,
            install_erased_state_file_fill,
            install_proprietary_efinfo_without_descriptor,
            install_record_aware_fill_pattern,
        )

        install_erased_state_file_fill()
        install_record_aware_fill_pattern()
        install_proprietary_efinfo_without_descriptor()
        install_body_encoding_against_creation_content()
    from pySim.esim.saip import File, templates
    from pySim.esim.saip.templates import FileTemplate

    default = bytes(range(20))
    literal = FileTemplate(0x6F99, "EF.TEST", "TR", None, 20, 5, 0x10, default.hex())
    cases = []
    for label, edits in (
        ("two differences", {3: 0xAA, 10: 0xBB}),
        ("three differences", {3: 0xAA, 10: 0xBB, 15: 0xCC}),
    ):
        body = bytearray(default)
        for position, value in edits.items():
            body[position] = value
        cases.append((f"20 B template default, {label}", literal, [("fileDescriptor", {})], bytes(body), default))
    pl = templates.FilesAtMF.files_by_pename["ef-pl"]
    pattern_fcp = {"fileDescriptor": b"\x41\x21", "efFileSize": b"\x02", "proprietaryEFInfo": {"fillPattern": b"\xaa"}}
    cases.append(("EF.PL fillPattern 'AA', body FFAA", pl, [("fileDescriptor", pattern_fcp)], bytes.fromhex("FFAA"), b"\xaa\xaa"))

    failures = 0
    for label, template_file, tuples, body, creation in cases:
        pe_file = File("repro", tuples, template_file)
        pe_file.body = body
        encoded = pe_file.file_content_to_tuples(optimize=True)
        card = _replay(creation, encoded)
        ok = card == body
        failures += 0 if ok else 1
        shown = [(key, value if isinstance(value, int) else value.hex().upper()) for key, value in encoded]
        print(f"{label}: {shown} -> card {card.hex().upper()} {'OK' if ok else 'WRONG'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
