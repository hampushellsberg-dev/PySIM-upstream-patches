# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Transcribe the SGP.22 Annex H ASN.1 module from the converted specification pages.

Reads ``docs/tel-docs/converted/<slug>/pages/page-NNN.md`` from the page that
opens "Annex H ASN.1 Definitions (Normative)" to the module's ``END``, drops the
page furniture, rejoins the comment text the PDF wrapped onto a new line, and
replaces the OPENTYPE information object class that asn1tools cannot resolve.
The output is pySim's ``pySim/esim/asn1/rsp_v3/rsp.asn``.

    python transcribe_annex_h.py SGP.22-v3.1 rsp.asn

A column-0 line after a comment line is a wrapped comment tail unless it is
code: an assignment, a closing brace, a tagged member, a named number such as
``missingCrl(9),`` (the published AuthenticateErrorCode sets those at column
0) or a comment line of its own. Joining a line that opens with ``--`` would
put a second ``--`` on the line, which ends the comment in ASN.1, so those
stay separate. Review the ``kept`` list the script prints when a new version
is transcribed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[2] / "docs" / "tel-docs" / "converted"
FURNITURE = re.compile(
    r"^(# Page \d+|```(text)?|\s*GSM Association\s+Non-confidential"
    r"|\s*RSP Technical Specification|\s*SGP\.22 v\d+\.\d+(\.\d+)?\s+Page \d+ of \d+)\s*$"
)
ANNEX_H = re.compile(r"^\s*Annex H\s+ASN\.1 Definitions \(Normative\)\s*$", re.M)
TAGGED_MEMBER = re.compile(r"^[a-z][\w-]*\s*\[(APPLICATION\s+|PRIVATE\s+|UNIVERSAL\s+)?\d+\]")
NAMED_NUMBER = re.compile(r"^[a-zA-Z][\w-]*\s*\(\s*\d+\s*\)\s*(,|$|--)")
OPENTYPE_CLASS = "OPENTYPE ::= CLASS {\n   &typeId OBJECT IDENTIFIER,\n   &Type\n}\n"
OPENTYPE_NOTE = (
    "-- The published module declares\n"
    "--    OPENTYPE ::= CLASS { &typeId OBJECT IDENTIFIER, &Type }\n"
    "-- and types the two fields of VendorSpecificExtension as OPENTYPE.&typeId and\n"
    "-- OPENTYPE.&Type. asn1tools cannot resolve an information object class, so they\n"
    "-- are OBJECT IDENTIFIER and ANY here, which encode the same on the wire.\n"
)
OPENTYPE_FIELDS = (
    ("vendorOid [0] OPENTYPE.&typeId, --", "vendorOid [0] OBJECT IDENTIFIER, -- OPENTYPE.&typeId in the published module;"),
    ("vendorSpecificData [1] OPENTYPE.&Type\n", "vendorSpecificData [1] ANY -- OPENTYPE.&Type in the published module\n"),
)


def module_lines(slug: str) -> list[str]:
    pages = LIBRARY / slug / "pages"
    numbers = sorted(int(p.stem[5:]) for p in pages.glob("page-*.md"))
    first = next(n for n in numbers if ANNEX_H.search((pages / f"page-{n:03d}.md").read_text()))
    lines: list[str] = []
    for number in numbers:
        if number < first:
            continue
        for line in (pages / f"page-{number:03d}.md").read_text().splitlines():
            if not FURNITURE.match(line):
                lines.append(line.rstrip())
        if any(line.strip() == "END" for line in lines):
            break
    start = next(i for i, line in enumerate(lines) if re.match(r"^\s*RSPDefinitions\s*\{", line))
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "END")
    return lines[start:end]


def rejoin_split_markers(lines: list[str]) -> list[str]:
    # The PDF text can break a '--' marker across two lines: '..., -' then '- Tag ...'.
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and re.search(r"[^-]\s-$", line) and lines[i + 1].lstrip().startswith("-"):
            out.append(line + lines[i + 1].lstrip())
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def join_split_identifiers(lines: list[str]) -> list[str]:
    # 'identified-' / 'organization(3)': an identifier the PDF hyphen-split at the line end.
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while "--" not in line and re.search(r"[A-Za-z]-$", line) and i + 1 < len(lines):
            i += 1
            line = line + lines[i].lstrip()
        out.append(line)
        i += 1
    return out


def rejoin_comment_tails(lines: list[str]) -> tuple[list[str], list[str]]:
    out: list[str] = []
    kept: list[str] = []
    after_comment = False
    for line in lines:
        column0 = bool(line) and not line[0].isspace()
        candidate = (after_comment and column0 and "::=" not in line
                     and not line.lstrip().startswith("}") and not TAGGED_MEMBER.match(line))
        if candidate and (line.startswith("--") or NAMED_NUMBER.match(line)):
            kept.append(line)
            candidate = False
        if candidate:
            out[-1] = out[-1].rstrip() + " " + line.strip()
            continue
        out.append(line.rstrip())
        after_comment = "--" in line
    return out, kept


def compact_blank_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() == "":
            following = next((later for later in lines[index + 1:] if later.strip()), "")
            preceding = next((earlier for earlier in reversed(out) if earlier.strip()), "")
            if following[:1].isspace() or following.lstrip().startswith("}"):
                continue
            if preceding.split("--", 1)[0].rstrip().endswith((",", "{")):
                continue
            if out and out[-1] == "":
                continue
        out.append(line)
    return out


def transcribe(slug: str) -> tuple[str, list[str]]:
    lines = join_split_identifiers(rejoin_split_markers(module_lines(slug)))
    lines, kept = rejoin_comment_tails(lines)
    text = "\n".join(compact_blank_lines(lines)) + "\n"
    if text.count(OPENTYPE_CLASS) != 1:
        raise ValueError("OPENTYPE class not found verbatim; check the VendorSpecificExtension pages")
    text = text.replace(OPENTYPE_CLASS, OPENTYPE_NOTE)
    for old, new in OPENTYPE_FIELDS:
        if text.count(old) != 1:
            raise ValueError(f"VendorSpecificExtension field not found verbatim: {old!r}")
        text = text.replace(old, new)
    for number, line in enumerate(text.splitlines(), 1):
        if line.count("--") > 1:
            raise ValueError(f"line {number} carries two '--' markers: {line!r}")
        if any(ord(char) > 127 for char in line):
            raise ValueError(f"line {number} is not ASCII: {line!r}")
    version = slug.split("-v", 1)[-1]
    preamble = (
        f"-- GSMA SGP.22 v{version}, Annex H \"ASN.1 Definitions (Normative)\", transcribed from the\n"
        "-- published specification. Comments the PDF wrapped onto a second line are\n"
        "-- rejoined; the one change to the definitions is described above\n"
        "-- VendorSpecificExtension.\n\n"
    )
    return preamble + text + "\nEND\n", kept


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    text, kept = transcribe(sys.argv[1])
    Path(sys.argv[2]).write_text(text)
    print(f"wrote {sys.argv[2]}: {len(text.splitlines())} lines")
    print("column-0 lines after a comment kept as lines of their own:")
    for line in kept:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
