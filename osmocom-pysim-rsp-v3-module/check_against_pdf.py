# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Check the rsp_v3 module against an independent pdftotext extraction of Annex H.

The transcription comes from a PDF-to-Markdown conversion of the specification;
this check reads the PDF itself, so a conversion defect cannot pass both sides.

    pdftotext -f 437 -l 462 -layout SGP.22-v3.1.pdf annexh.txt
    python check_against_pdf.py pySim/esim/asn1/rsp_v3/rsp.asn annexh.txt

Two alignments, whitespace-insensitive:

1. code: comments removed, version markers (#SupportedFromV3.0.0# ...) kept as
   tokens. The PDF side may only add prose, the comment text the PDF wrapped
   onto a line of its own; every other difference is printed.
2. full text: comments included, '--' and line breaks ignored. Prints every
   difference.

The expected differences are the OPENTYPE replacement in VendorSpecificExtension
and the transcription notes describing it and the module's origin.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

FURNITURE = re.compile(
    r"^\s*(GSM Association\s+Non-confidential|RSP Technical Specification|SGP\.22 v\d+(\.\d+)*\s+Page \d+ of \d+"
    r"|Annex H\s+ASN\.1 Definitions \(Normative\))\s*$")
MARKER = re.compile(r"#[A-Za-z]+V\d+(\.\d+)*#")
TOKEN = re.compile(r"::=|\.\.\.|\.\.|[{}()\[\],;|]|[^\s{}()\[\],;|]+")
# what makes an insertion code rather than prose: brackets, keywords, a named number such as
# missingCrl(9), or a version marker
CODE_HINT = re.compile(r"::=|[{}\[\]]|\b(OPTIONAL|DEFAULT|SEQUENCE|CHOICE|OCTET|INTEGER|BOOLEAN|ENUMERATED|"
                       r"UTF8String|IA5String|NULL|SIZE|OBJECT|IDENTIFIER|BIT|STRING)\b|"
                       r"[A-Za-z][\w-]*\s*\(\s*\d+\s*\)|#[A-Za-z]+V\d")


def strip_comment(line: str) -> tuple[str, list[str]]:
    """Code part of a line and the markers its comments carry ('--' ends at EOL or the next '--')."""
    code: list[str] = []
    markers: list[str] = []
    i = 0
    while i < len(line):
        j = line.find("--", i)
        if j < 0:
            code.append(line[i:])
            break
        code.append(line[i:j])
        k = line.find("--", j + 2)
        comment = line[j + 2:] if k < 0 else line[j + 2:k]
        markers += [m.group(0) for m in MARKER.finditer(comment)]
        if k < 0:
            break
        i = k + 2
    return " ".join(code), markers


def module_lines(path: Path) -> list[str]:
    text = re.sub(r"/\*.*?\*/", " ", path.read_text(encoding="utf-8"), flags=re.S)
    return text.splitlines()


def pdf_lines(path: Path) -> list[str]:
    raw = [line.replace("\f", "") for line in path.read_text(encoding="utf-8").splitlines()]
    joined: list[str] = []
    for line in raw:
        if FURNITURE.match(line):
            continue
        # a name the PDF broke after its own hyphen ("identified-" / "organization(3)")
        if joined and re.search(r"[A-Za-z0-9]-$", joined[-1]) and "--" not in joined[-1]:
            joined[-1] = joined[-1].rstrip() + line.strip()
        else:
            joined.append(line)
    return joined


def code_tokens(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        code, markers = strip_comment(line)
        out += TOKEN.findall(code) + markers
    return out


def text_tokens(lines: list[str]) -> list[str]:
    return [w for line in lines for w in TOKEN.findall(line.replace("--", " "))]


def report(title: str, mod: list[str], pdf: list[str], skip_prose: bool) -> int:
    print(f"== {title}: module {len(mod)} tokens, PDF {len(pdf)} tokens")
    shown = prose = 0
    for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, mod, pdf, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if skip_prose and op == "insert" and not CODE_HINT.search(" ".join(pdf[b0:b1])):
            prose += 1
            continue
        shown += 1
        print(f"  {op} after ...{' '.join(mod[max(0, a0 - 6):a0])[-70:]}")
        if a1 > a0:
            print(f"    module: {' '.join(mod[a0:a1])[:200]}")
        if b1 > b0:
            print(f"    PDF:    {' '.join(pdf[b0:b1])[:200]}")
    if skip_prose:
        print(f"  ({prose} insertions of wrapped comment prose not shown)")
    print(f"  {shown} differences shown")
    return shown


def main() -> int:
    module = module_lines(Path(sys.argv[1]))
    pdf = pdf_lines(Path(sys.argv[2]))
    report("code and version markers", code_tokens(module), code_tokens(pdf), skip_prose=True)
    report("full text", text_tokens(module), text_tokens(pdf), skip_prose=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
