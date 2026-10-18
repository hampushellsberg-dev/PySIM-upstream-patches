# pySim: `File.from_fileDescriptor` ignores `proprietaryEFInfo` unless the Fcp repeats `fileDescriptor`

## What happens

`pySim/esim/saip/__init__.py`, `File.from_fileDescriptor` reads the Fcp's
`proprietaryEFInfo` up front but applies it -- the special file information,
the fill or repeat pattern and a BER-TLV maximum file size -- only inside the
branch that decodes the Fcp's own `fileDescriptor`:

```python
        pefi = fileDescriptor.get('proprietaryEFInfo', {})
        ...
        if 'fileDescriptor' in fileDescriptor:
            ...
            if fdb_dec['file_type'] == 'working_ef':
                ...
                if 'repeatPattern' in pefi:
                    self.fill_pattern = pefi['repeatPattern']
                    self.fill_pattern_repeat = True
                if 'fillPattern' in pefi:
                    self.fill_pattern = pefi['fillPattern']
                    self.fill_pattern_repeat = False
```

A file a profile template defines takes its structure from the template
(`File.from_template`), and a PE that changes only the pattern names only
`proprietaryEFInfo` in the file's Fcp. pySim then keeps `fill_pattern` at
`None`, so `File.body` is the template default, or nothing at all when the
template defines none, where the eUICC holds the pattern.

## Why it is wrong

TCA eUICC Profile Package Interoperable Format Technical Specification
V3.4.1, section 8.3.3 (pages 29 and 30): "To overwrite parameters of the
template, the following parameters may be specified within the FCP parameters
defined within a PE." The table lists `proprietaryEFInfo` as optional for an
EF, and the text below it: "A repeat or fill pattern provided within the
respective "Fcp" shall overwrite the default content completely" and "If
parameter "proprietaryEFInfo" is provided and no repeat or fill pattern are
present, the default template fill or repeat pattern shall be used." Nothing
ties the pattern to a repeated `fileDescriptor`; changing the file type in
byte 1 of it is not even allowed.

## Repro

`repro_proprietary_efinfo.py` builds a `File` from a TCA template file and an
Fcp that sets only the pattern (pinned pySim from the YggdraSIM venv):

```
## pinned pySim
EF.UMPC fillPattern '01FF': fill_pattern=None body=(empty) -> WRONG
EF.PL fillPattern 'AA': fill_pattern=None body=FFFF -> WRONG
EF.PNN fillPattern '00FF': fill_pattern=None body=(empty) -> WRONG
## pinned pySim + YggdraSIM compensation (--compensated)
EF.UMPC fillPattern '01FF': fill_pattern=01FF body=01FFFFFFFF -> OK
EF.PL fillPattern 'AA': fill_pattern=AA body=AAAA -> OK
EF.PNN fillPattern '00FF': fill_pattern=00FF body=00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00FFFFFF... -> OK
## pinned pySim with this patch and pysim-saip-record-aware-fill-pattern.patch
EF.UMPC fillPattern '01FF': fill_pattern=01FF body=01FFFFFFFF -> OK
EF.PL fillPattern 'AA': fill_pattern=AA body=AAAA -> OK
EF.PNN fillPattern '00FF': fill_pattern=00FF body=00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00FFFFFF... -> OK
```

With this patch alone EF.PNN reads the pattern but still lays it once across
the file; the per-record expansion is bug 2 of
`upstream_patches/osmocom-pysim-saip-fill-file-offset-erased-state/`.

## Fix

`0001-saip-read-proprietary-efinfo-without-file-descriptor.patch` moves the
`proprietaryEFInfo` handling out of the `fileDescriptor` branch: it applies to
any working EF whose type is known, from the Fcp's descriptor or from the
template, in the same order as before (repeat pattern, then fill pattern).

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_proprietary_efinfo_without_descriptor`
wraps `File.from_fileDescriptor`. It calls upstream first and, for an Fcp
without `fileDescriptor` on a working EF the template typed, applies the same
members in the same order, then checks the file reports the declared pattern
and raises `SaipProprietaryInfoMismatch` otherwise. Once upstream applies them
itself the assignments change nothing. `saip_json_codec` and
`SIMCARD/saip_pysim_specs.py` install it beside the other SAIP compensations.
`tests/test_saip_pysim_compat.py` pins the unpatched callable through
`__wrapped__`, so it fails the day the pin moves to a pySim with the fix.

The workbench's FCP rows write exactly this shape: setting a fill pattern on a
template file adds `proprietaryEFInfo.fillPattern` to its Fcp and nothing else.

## Stress checklist

- [x] Transparent template EF without a default (EF.UMPC): the pattern fills the declared size.
- [x] Transparent template EF with a default (EF.PL): the Fcp pattern replaces the default.
- [x] Linear fixed template EF (EF.PNN): the pattern opens every record with the record-aware compensation.
- [x] An Fcp that repeats `fileDescriptor`: upstream's own path, unchanged.
- [x] A DF and a generic-file-management file (whose `createFCP` always carries a descriptor): unchanged.
- [x] Content written over the pattern still lands on top of it.
- [ ] Upstream merge request.
