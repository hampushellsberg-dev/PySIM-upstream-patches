# pySim: `File.from_fileDescriptor` keeps the template record count over `efFileSize`

## What happens

`pySim/esim/saip/__init__.py`, `File.from_template` copies `nb_rec` from the
TCA template (`FileTemplate(0x6f40, 'EF.MSISDN', 'LF', 1, 24, ...)` gives one
record) and `File.from_fileDescriptor` only recomputes the count from the
profile's `efFileSize` while `self.nb_rec` is still `None`:

```python
                if efFileSize:
                    if self.rec_len and self.nb_rec == None:
                        # compute the number of records from file size and record length
                        self.nb_rec = self._file_size // self.rec_len
```

A profile whose `fileDescriptor` omits the number of records (the 4-byte
form `42 21 00 22`) but declares `efFileSize` 68 therefore keeps the
template's single record: `nb_rec == 1`, `file_size == 34`, and the second
34-byte record is invisible to anything that walks the file by record.
ETSI TS 102 222 sizes a linear fixed EF as record length times record
count, so the declared size is the count when the descriptor is silent.

## Repro

`repro_record_count.py` (run on the pinned pySim from the YggdraSIM venv):

```
template EF.MSISDN: nb_rec=1 rec_len=24
pySim after from_fileDescriptor: nb_rec=1 rec_len=34 file_size=34
YggdraSIM compensation: nb_rec=2 file_size=68
```

Expected after the fix: `nb_rec=2 file_size=68` from pySim itself.

## Fix

`0001-saip-file-descriptor-size-wins-over-template-count.patch`: when the
descriptor carries no record count, derive it from `efFileSize` even if the
template supplied one.

## Companion patch for pySim master

`smsp-tp-sc-addr-record-1.patch` goes in first. `SmspTpScAddr`
(`pySim/esim/saip/personalization.py`, since `0fe432f`) decodes the whole
EF.SMSP body as record 1 and writes one record back as the whole body. The
TS.48 v5 profiles in `smdpp-data/upp` declare EF.SMSP with the 4-byte
`fileDescriptor` `42 21 00 2A` (record length 42, no record count) and
`efFileSize` 84. Once the record count follows `efFileSize` the body holds
both records, the single-record decode fails (`UnicodeDecodeError:
'gsm03.38' codec can't decode byte 0xff in position 0`), and
`tests/unittests/test_configurable_parameters.py` on master, which
personalises those profiles, fails with it. The companion decodes and
encodes record 1 only and keeps the records after it: the test passes with
and without the record count fix, and personalising one of those profiles
keeps both records (84 bytes) with record 2 unchanged.

## YggdraSIM-side compensation

`yggdrasim_common/gui_server/actions/saip.py::_record_count_from_declared_size`
returns the largest of the template count, the declared size and the body,
so the file view lists every record. It states its result and becomes a
no-op once pySim honours the size (its own count then equals the declared
one). `tests/test_saip_ef_length_fields.py` and the GUI record surfaces
depend on it.

## Stress checklist

- [x] Template file with a 4-byte descriptor and a larger `efFileSize` (EF.MSISDN, two records).
- [x] Template file with a 5-byte descriptor carrying the count (unchanged).
- [x] Generic-file-management file without a template (count from the descriptor or the body).
- [x] Transparent EF (`rec_len` None): untouched.
- [x] pySim master `9aa8934`: `test_configurable_parameters` with the companion patch, before and after the fix.
- [ ] Upstream merge request.
