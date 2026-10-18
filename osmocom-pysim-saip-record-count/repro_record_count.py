# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.
"""Repro: pySim keeps the template record count over the profile's file size.

``File.from_template`` copies ``nb_rec`` from the TCA template and
``from_fileDescriptor`` recomputes it from ``efFileSize`` only while it is
still ``None``, so a profile whose descriptor omits the record count but
declares a larger size keeps the template default. Run on the pinned
pySim; the YggdraSIM compensation is printed next to it.
"""

from __future__ import annotations

from pySim.esim.saip import File
from pySim.esim.saip.templates import ProfileTemplateRegistry

from yggdrasim_common.gui_server.actions.saip import _record_count_from_declared_size

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
body = b"\xff" * 68
count, size = _record_count_from_declared_size(pe_file, body, pe_file.rec_len, pe_file.nb_rec, pe_file.file_size)
print("YggdraSIM compensation: nb_rec=%s file_size=%s" % (count, size))
assert count == 2 and size == 68
