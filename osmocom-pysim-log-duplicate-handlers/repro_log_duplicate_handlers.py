# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Repro: pySim prints each secure-channel log record twice.

Calls pySim's SCP03 key derivation once and counts the lines it prints to
stdout. ``PySimLogger.get`` gives both ``pySim.global_platform`` and
``pySim.global_platform.scp`` a print handler, and a record of the child
propagates to the parent's handler as well.

    python repro_log_duplicate_handlers.py                # the pySim on the path
    python repro_log_duplicate_handlers.py --compensated  # with the YggdraSIM gate, debug flag on
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path


def main() -> int:
    compensated = "--compensated" in sys.argv[1:]
    if compensated:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        os.environ["YGGDRASIM_GLOBAL_DEBUG"] = "1"
    from pySim.global_platform.scp import scp03_key_derivation

    if compensated:
        from yggdrasim_common.pysim_log_gate import install_pysim_secure_channel_log_gate

        install_pysim_secure_channel_log_gate()
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        scp03_key_derivation(b"\x04", bytes(16), bytes(range(16)), 128)
    lines = captured.getvalue().splitlines()
    print(f"mode: {'YggdraSIM gate, debug flag on' if compensated else 'pySim as installed'}")
    for line in lines:
        print(f"  printed: {line[:96]}")
    print(f"{len(lines)} line(s) for one log record -> {'OK' if len(lines) <= 1 else 'DUPLICATED'}")
    return 0 if len(lines) <= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
