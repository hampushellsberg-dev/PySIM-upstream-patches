# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.
from __future__ import annotations

import os
import sys
from collections import OrderedDict
from pathlib import Path


def _ensure_workspace_pysim() -> None:
    override = os.environ.get("YGGDRASIM_REPRO_PYSIM_ROOT")
    if override:
        sys.path.insert(0, override)
        return

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            pysim_root = parent / "pysim"
            if pysim_root.is_dir():
                sys.path.insert(0, str(pysim_root))
            return


_ensure_workspace_pysim()

from pySim.esim.saip import (
    ProfileElementMF,
    ProfileElementSequence,
    ProfileElementTelecom,
    oid,
)


def main() -> None:
    seq = ProfileElementSequence()

    mf = ProfileElementMF(
        OrderedDict(
            [
                ("templateID", str(oid.MF)),
                ("mf", []),
            ]
        ),
        pe_sequence=seq,
    )
    seq.pe_list.append(mf)
    mf._post_decode()

    telecom = ProfileElementTelecom(
        OrderedDict(
            [
                ("templateID", str(oid.DF_TELECOM_v2)),
                ("df-telecom", []),
                ("ef-pbr", []),
                (
                    "ef-pbc",
                    [
                        (
                            "fileDescriptor",
                            {"fileID": b"\x4f\x09", "efFileSize": b"\x02"},
                        ),
                    ],
                ),
            ]
        ),
        pe_sequence=seq,
    )
    telecom._post_decode()

    node = seq.mf.lookup_by_fidpath([0x3F00, 0x7F10, 0x5F3A, 0x4F30])
    print(node.fid_path_str)
    node = seq.mf.lookup_by_fidpath([0x3F00, 0x7F10, 0x5F3A, 0x4F09])
    print(node.fid_path_str)


if __name__ == "__main__":
    main()
