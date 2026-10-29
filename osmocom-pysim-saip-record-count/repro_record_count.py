# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.
"""Repro: pySim keeps the template record count over the profile's file size.

``File.from_template`` copies ``nb_rec`` from the TCA template and
``from_fileDescriptor`` recomputes it from ``efFileSize`` only while it is
still ``None``, so a profile whose descriptor omits the record count but
declares a larger size keeps the template default. Exits non-zero while
the pySim on the path keeps the template count. (The YggdraSIM-side
compensation that used to be printed here was retired on 2026-10-23, when
YggdraSIM pinned hampushellsberg-dev/pysim, which carries this fix.)
"""

from __future__ import annotations

from pySim.esim.saip import File
from pySim.esim.saip.templates import ProfileTemplateRegistry

template = None
for candidate in ProfileTemplateRegistry.by_oid.values():
    entry = getattr(candidate, "files_by_pename", {}).get("ef-msisdn")
    if entry is not None:
        template = entry
        break
assert template is not None, "no template carries ef-msisdn"
print("template EF.MSISDN: nb_rec=%s rec_len=%s" % (template.nb_rec, template.rec_len))

pe_file = File("ef-msisdn", template=template)
# Profile FCP: linear fixed, 34-byte records, no record count, 68 bytes.
pe_file.from_fileDescriptor({"fileDescriptor": bytes.fromhex("42210022"), "efFileSize": b"\x44"})
print("pySim after from_fileDescriptor: nb_rec=%s rec_len=%s file_size=%s"
      % (pe_file.nb_rec, pe_file.rec_len, pe_file.file_size))
fixed = pe_file.nb_rec == 2 and pe_file.file_size == 68
print("OK" if fixed else "WRONG: the template count won over efFileSize")
raise SystemExit(0 if fixed else 1)
