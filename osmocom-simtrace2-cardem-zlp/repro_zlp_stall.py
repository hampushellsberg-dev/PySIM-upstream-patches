# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Journal repro: modem TPDUs whose cardem USB message fills whole packets arrive late.

Reads the HIL bridge journal (``journalctl --user -u
yggdrasim-hil-supervisor.service -o short-iso-precise``) on stdin. A
SIMtrace2 cardem board forwards a modem command's data in one RX-DATA
message of 14 + Lc bytes; firmware with the bug ends a 128-, 192- or
256-byte message without a zero-length packet, so the host sees it only
when the board sends its next message. Two reports:

- every modem TPDU with command data, split by whether its message is a
  whole number of 64-byte packets, and how many of each were held: a
  continuation command that reached the bridge after a modem reset or more
  than 100 s after the previous answer;
- every burst of RECEIVE DATA reads (the card draining one server response,
  ending at a read that leaves 0 bytes buffered), and which bursts ended in
  a read of 97, 160 or 224 bytes: the TERMINAL RESPONSE carrying those is
  114, 178 or 242 bytes of command data.

Standalone: no YggdraSIM imports.
"""
from __future__ import annotations

import collections
import datetime
import re
import sys
from typing import Iterator

STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)")
RX_DATA_OVERHEAD = 14
BULK_PACKET_SIZE = 64
HELD_SECONDS = 100.0
# FETCH, TERMINAL RESPONSE, GET RESPONSE: each answers something the card
# said just before, so one arriving after a reset or minutes late was held.
CONTINUATION_INS = (0x12, 0x14, 0xC0)


def unterminated(lc: int) -> bool:
    size = RX_DATA_OVERHEAD + lc
    return size > BULK_PACKET_SIZE and size % BULK_PACKET_SIZE == 0


def comprehension_tlvs(data: bytes) -> Iterator[tuple[int, bytes]]:
    offset = 0
    while offset + 2 <= len(data):
        tag = data[offset] & 0x7F
        length = data[offset + 1]
        offset += 2
        if length == 0x81:
            length = data[offset]
            offset += 1
        yield tag, data[offset:offset + length]
        offset += length


def main() -> int:
    last_answer: datetime.datetime | None = None
    reset_since = False
    by_kind: dict[bool, list[tuple[str, int, float, bool, bool]]] = collections.defaultdict(list)
    bursts: list[tuple[str, tuple[int, ...]]] = []
    reads: list[int] = []
    for line in sys.stdin:
        match = STAMP.match(line)
        if match is None:
            continue
        when = datetime.datetime.fromisoformat(match.group(1))
        if "Card -> modem APDU" in line or "Bridge -> modem" in line:
            last_answer = when
            reset_since = False
            continue
        if "Modem reset the UICC" in line or "Reset card for modem session" in line:
            reset_since = True
            continue
        if "Modem -> bridge APDU" not in line:
            continue
        apdu = bytes.fromhex(line.split("Modem -> bridge APDU", 1)[1].split()[0])
        if len(apdu) <= 5 or apdu[4] != len(apdu) - 5:
            continue
        lc = apdu[4]
        gap = (when - last_answer).total_seconds() if last_answer is not None else -1.0
        held = apdu[1] in CONTINUATION_INS and (reset_since or gap > HELD_SECONDS)
        by_kind[unterminated(lc)].append((match.group(1)[:19], lc, gap, reset_since, held))
        if apdu[1] != 0x14:
            continue
        fields = dict(comprehension_tlvs(apdu[5:]))
        details = fields.get(0x01, b"")
        if len(details) < 2 or details[1] != 0x42 or 0x36 not in fields:
            continue
        reads.append(len(fields[0x36]))
        if fields.get(0x37, b"\xff")[:1] == b"\x00":
            bursts.append((match.group(1)[:10], tuple(reads)))
            reads = []

    for whole_packets in (True, False):
        entries = by_kind[whole_packets]
        held = [entry for entry in entries if entry[4]]
        label = "unterminated message" if whole_packets else "other lengths"
        print(f"{label}: {len(entries)} TPDUs, {len(held)} held")
        for stamp, lc, gap, reset, is_held in entries if whole_packets else held:
            print(
                f"  {stamp}  Lc=0x{lc:02X}  {gap:7.1f} s after the last answer  "
                f"reset_between={reset}  held={is_held}"
            )

    endings = collections.Counter(burst[1][-1] for burst in bursts)
    hit = [burst for burst in bursts if burst[1][-1] in (97, 160, 224)]
    print(f"RECEIVE DATA bursts: {len(bursts)}, ending in 97/160/224 bytes: {len(hit)}")
    for (day, shape), count in sorted(collections.Counter(hit).items()):
        print(f"  {day}  {count}x  reads={list(shape)}  total={sum(shape)}")
    print("most common last reads:", endings.most_common(8))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
