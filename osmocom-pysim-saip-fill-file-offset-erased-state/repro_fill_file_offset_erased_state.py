#!/usr/bin/env python3
"""Standalone repro: pySim NUL-fills the gaps a SAIP fillFileOffset skips.

Run against a stock pySim to see the failures, then against a tree carrying
``pysim-saip-fill-file-offset-erased-state.patch`` to see them pass. No
YggdraSIM imports -- this file is meant to travel with the upstream report.

TCA "Profile interoperability technical specification" V3.4.1:
  - 8.3.5   fillFileOffset moves the write pointer; it writes nothing.
  - 8.3.3   the tuple list has the effect of creating the file with a
            fill/repeat pattern (or non-pattern content) and then updating it.
  - 9.10    the default EF-ARR image is "truncated or padded with 'FF...FF'".
  - 9.10.3.3 worked example: EF-ARR as fillPattern 'FF'H plus six
            fillFileOffset / fillFileContent pairs.
"""

import sys

from pySim.esim.saip import File
from pySim.esim.saip.templates import FileTemplate

FF = 0xFF


def build(pename, descriptor, tuples, template=None):
    return File(pename, [("fileDescriptor", descriptor)] + tuples if descriptor else tuples,
                template)


def case_no_template():
    """EF.ARR from a raw PE with no resolvable template -- gaps must be FF."""
    descriptor = {
        "fileDescriptor": bytes.fromhex("42210031"),
        "securityAttributesReferenced": bytes.fromhex("01"),
        "efFileSize": bytes.fromhex("0341"),
    }
    tuples = [
        ("fillFileContent", bytes.fromhex(
            "8001019000800102A40683010A9501088401D4A40683010A95010880017C9700")),
        ("fillFileOffset", 17),
        ("fillFileContent", bytes.fromhex("80017F9700")),
    ]
    body = build("EF.ARR", descriptor, tuples).body
    return "no template", body, body[32:49] == bytes([FF]) * 17


def case_template_without_default():
    """Template present, no default_val -- the stream is still empty at step 1."""
    template = FileTemplate(0x6F06, "EF.ARR", "LF", 4, 8, 1)
    tuples = [("fillFileOffset", 8), ("fillFileContent", bytes.fromhex("8001019000"))]
    body = build("EF.ARR", None, tuples, template).body
    return "template, no default_val", body, body[0:8] == bytes([FF]) * 8


def case_short_literal_default():
    """A non-'...' default_val shorter than its record is returned unexpanded, leaving a growable tail."""
    template = FileTemplate(0x6F99, "EF.T", "LF", 4, 6, 1, None, "AABBCCDD")
    tuples = [("fillFileOffset", 8), ("fillFileContent", bytes.fromhex("1122"))]
    body = build("EF.T", None, tuples, template).body
    return "short literal default_val", body, body[4:8] == bytes([FF]) * 4


def case_spec_9_10_3_3():
    """TCA SAIP 9.10.3.3 -- six access rules, each FF-padded to 37 B."""
    descriptor = {
        "fileDescriptor": bytes.fromhex("42210025"),
        "efFileSize": bytes.fromhex("00DE"),
        "proprietaryEFInfo": {"fillPattern": bytes.fromhex("FF")},
    }
    tuples = []
    for key, value in (
        ("fillFileContent", "8001019000800102A406830101950108800158A40683010A950108"),
        ("fillFileOffset", 10),
        ("fillFileContent", "800101A40683010195010880015AA40683010A950108"),
        ("fillFileOffset", 15),
        ("fillFileContent", "80015BA40683010A950108"),
        ("fillFileOffset", 26),
        ("fillFileContent", "800101900080015A9700"),
        ("fillFileOffset", 27),
        ("fillFileContent", "800103A406830101950108800158A40683010A950108"),
        ("fillFileOffset", 15),
        ("fillFileContent", "800111A40683010195010880014AA40683010A950108"),
    ):
        tuples.append((key, bytes.fromhex(value) if key == "fillFileContent" else value))
    body = build("EF.ARR", descriptor, tuples).body
    expected = b"".join(
        bytes.fromhex(rule).ljust(37, b"\xff") for rule in (
            "8001019000800102A406830101950108800158A40683010A950108",
            "800101A40683010195010880015AA40683010A950108",
            "80015BA40683010A950108",
            "800101900080015A9700",
            "800103A406830101950108800158A40683010A950108",
            "800111A40683010195010880014AA40683010A950108",
        )
    )
    return "spec 9.10.3.3 example", body, body == expected


def case_zero_fill_pattern():
    """fillPattern '00'H -- a written zero is content and must survive."""
    descriptor = {
        "fileDescriptor": bytes.fromhex("42210008"),
        "efFileSize": bytes.fromhex("0010"),
        "proprietaryEFInfo": {"fillPattern": bytes.fromhex("00")},
    }
    tuples = [("fillFileOffset", 8), ("fillFileContent", bytes.fromhex("AABB"))]
    body = build("EF.Z", descriptor, tuples).body
    return "fillPattern '00'H", body, body == bytes.fromhex("0000000000000000AABB000000000000")


def case_reencode_stability():
    """Decode -> file_content_to_tuples(optimize=True) -> decode must be stable."""
    descriptor = {
        "fileDescriptor": bytes.fromhex("42210031"),
        "efFileSize": bytes.fromhex("0062"),
    }
    tuples = [
        ("fillFileContent", bytes.fromhex("8001019000800102A406830101950108")),
        ("fillFileOffset", 33),
        ("fillFileContent", bytes.fromhex("80017F9700")),
    ]
    first = build("EF.ARR", descriptor, tuples)
    reencoded = first.file_content_to_tuples(optimize=True)
    second = build("EF.ARR", descriptor, list(reencoded))
    explicit_nuls = any(
        key == "fillFileContent" and b"\x00\x00\x00\x00" in value
        for key, value in reencoded
    )
    return (
        "re-encode stability",
        second.body,
        first.body == second.body and not explicit_nuls,
    )


CASES = (
    case_no_template,
    case_template_without_default,
    case_short_literal_default,
    case_spec_9_10_3_3,
    case_zero_fill_pattern,
    case_reencode_stability,
)


def main() -> int:
    failures = 0
    for case in CASES:
        label, body, ok = case()
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        print(f"         {body.hex().upper()}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} cases pass")
    return 1 if failures else 0




# --- Bug 2: a fill/repeat pattern is applied once per file, not per record ---
#
# TS 102 222 6.3.2.2 tag 'C1' initialises "the first W-1 bytes of each record of
# a record oriented EF"; tag 'C2' repeats within a record and truncates there.


def _patterned(file_type, rec_len, nb_rec, pattern, repeat=False):
    handle = File("ef-probe", None)
    handle.file_type = file_type
    handle.rec_len = rec_len
    handle.nb_rec = nb_rec
    handle.fill_pattern = bytes.fromhex(pattern)
    handle.fill_pattern_repeat = repeat
    return handle


def case_c1_opens_every_record():
    """EF.EXT2 shape: 3 x 13 B with fillPattern '00FF'H."""
    body = _patterned("LF", 13, 3, "00FF").expand_fill_pattern()
    return "C1 per record", body, body == (b"\x00" + b"\xff" * 12) * 3


def case_c2_truncates_at_the_record_boundary():
    """A 3 B repeat pattern in a 4 B record restarts at each record."""
    body = _patterned("CY", 4, 2, "AABBCC", repeat=True).expand_fill_pattern()
    return "C2 per record", body, body == bytes.fromhex("AABBCCAA") * 2


def case_pattern_longer_than_the_record():
    """'If the file or record length is shorter ... shall be truncated.'"""
    body = _patterned("LF", 2, 2, "0011223344").expand_fill_pattern()
    return "C1 truncation", body, body == bytes.fromhex("00110011")


CASES = CASES + (
    case_c1_opens_every_record,
    case_c2_truncates_at_the_record_boundary,
    case_pattern_longer_than_the_record,
)



# --- Bug 3: a record template's default value is expanded once per file, not per record ---
#
# SAIP V3.4.1 section 9: EF ICI (page 86) is 20 records of 38 bytes with the
# default 'FF...FF 0000000001FFFF' -- one record. FileTemplate._default_value_len
# already returns rec_len for LF / CY; file_content_from_tuples expands over
# file_size instead.


def case_template_default_per_record():
    """EF ICI shape, two records: the default's tail must close every record."""
    template = FileTemplate(0x6F80, "EF.ICI", "CY", 2, 38, 5, 0x14, "FF...FF0000000001FFFF")
    record = b"\xff" * 31 + bytes.fromhex("0000000001FFFF")
    body = File("ef-ici", [("fillFileContent", b"\x11")], template).body
    return "template default per record", body, body == b"\x11" + record[1:] + record


CASES = CASES + (case_template_default_per_record,)


if __name__ == "__main__":
    sys.exit(main())
