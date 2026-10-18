# pySim: `File.file_content_to_tuples(optimize=True)` does not rebuild the body on the card

## What happens

`pySim/esim/saip/__init__.py`, `File.file_content_to_tuples(optimize=True)`
encodes only where a file's body differs from a baseline, as
`fillFileOffset` / `fillFileContent` tuples. Two parts of it disagree with the
specification:

```python
        if self.template:
            default = self.template.expand_default_value_pattern(length=len(self.body))
            ...
                sm = SequenceMatcher(a=default, b=self.body)
        ...
        cur = 0
        for block in non_matching_blocks:
            ret.append(('fillFileOffset', block.a - cur))
            ret.append(('fillFileContent', self.body[block.a:block.a+block.size]))
            cur += block.size
```

1. The baseline is the template default, or 'FF' bytes, and never the file's
   own Fcp fill or repeat pattern (`self.fill_pattern`). A byte the body shares
   with the template default but not with the pattern is left out, and the
   eUICC keeps the pattern there.
2. `cur` grows by the sizes written, so `block.a - cur` is an offset from the
   end of the bytes written so far, not from the pointer. Every block after
   the first lands too far into the file, and a later one can land past its end.

## Why it is wrong

TCA eUICC Profile Package Interoperable Format Technical Specification V3.4.1:

- section 8.3.3 (page 30): "A repeat or fill pattern provided within the
  respective "Fcp" shall overwrite the default content completely", and
  content "within "fillFileContent" / "fillFileOffset" shall have the same
  effect as creating a file with a fill/repeat pattern [...] and thereafter
  updating the content via Update" -- the baseline is what the file is created
  with;
- section 8.3.5 (page 45): "There is always a current "fillFileOffset"
  pointer", and in the worked example a content write leaves it at byte 22 and
  "fillFileOffset: 24 sets "fillFilePointer" pointer to [...] (Byte 46)" -- the
  offset moves the pointer from where it stands, and a write moves it past the
  bytes written.

## Repro

`repro_optimised_body_encoding.py` encodes a body and replays the tuples onto
the content the file is created with, the way section 8.3.5 reads them:

```
## pinned pySim
20 B template default, two differences: [('fillFileOffset', 3), ('fillFileContent', 'AA'), ('fillFileOffset', 9), ('fillFileContent', 'BB')] -> card 000102AA0405060708090A0B0CBB0E0F10111213 WRONG
20 B template default, three differences: [('fillFileOffset', 3), ('fillFileContent', 'AA'), ('fillFileOffset', 9), ('fillFileContent', 'BB'), ('fillFileOffset', 13), ('fillFileContent', 'CC')] -> card 000102AA0405060708090A0B0CBB0E0F10111213FFFFFFFFFFFFFFCC WRONG
EF.PL fillPattern 'AA', body FFAA: [('fillFileOffset', 1), ('fillFileContent', 'AA')] -> card AAAA WRONG
## pinned pySim + YggdraSIM compensation (--compensated)
20 B template default, two differences: [('fillFileOffset', 3), ('fillFileContent', 'AA'), ('fillFileOffset', 6), ('fillFileContent', 'BB')] -> card 000102AA040506070809BB0B0C0D0E0F10111213 OK
20 B template default, three differences: [('fillFileOffset', 3), ('fillFileContent', 'AA'), ('fillFileOffset', 6), ('fillFileContent', 'BB'), ('fillFileOffset', 4), ('fillFileContent', 'CC')] -> card 000102AA040506070809BB0B0C0D0ECC10111213 OK
EF.PL fillPattern 'AA', body FFAA: [('fillFileOffset', 0), ('fillFileContent', 'FF')] -> card FFAA OK
## pinned pySim with this patch (and the two record / descriptor patches)
20 B template default, two differences: [('fillFileOffset', 3), ('fillFileContent', 'AA'), ('fillFileOffset', 6), ('fillFileContent', 'BB')] -> card 000102AA040506070809BB0B0C0D0E0F10111213 OK
20 B template default, three differences: [('fillFileOffset', 3), ('fillFileContent', 'AA'), ('fillFileOffset', 6), ('fillFileContent', 'BB'), ('fillFileOffset', 4), ('fillFileContent', 'CC')] -> card 000102AA040506070809BB0B0C0D0ECC10111213 OK
EF.PL fillPattern 'AA', body FFAA: [('fillFileOffset', 0), ('fillFileContent', 'FFAA')] -> card FFAA OK
```

The EF.PL case carries its descriptor in the Fcp so that the pinned pySim reads
the pattern at all (see
`upstream_patches/osmocom-pysim-saip-proprietary-efinfo-without-descriptor/`).

## Fix

`0001-saip-encode-body-against-creation-content-with-relative-offsets.patch`:
take the baseline from `expand_fill_pattern()` when the Fcp declares a pattern,
and advance `cur` to the end of each block written.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_body_encoding_against_creation_content`
wraps `File.file_content_to_tuples`. It calls upstream first and replays the
result onto the content the card creates the file with (the Fcp pattern, else
the template default, per record with the record-aware compensations, erased
beyond). When that rebuilds the body, upstream's tuples stand -- every
unoptimised call, and every call once upstream has the fix. Otherwise it
encodes the positional differences with relative offsets, replays them too,
and raises `SaipBodyEncodingMismatch` if they do not rebuild the body.
`saip_json_codec` installs it with the other SAIP compensations, and the
workbench's body editors (`saip.update_file_content`,
`saip.update_record_bytes`) encode a template file through it.
`tests/test_saip_pysim_compat.py` pins the unpatched callable through
`__wrapped__`.

## Stress checklist

- [x] Two and three differences against a non-uniform template default rebuild the body.
- [x] A body equal to the creation content encodes as no tuples.
- [x] An Fcp pattern is the baseline: a byte equal to the template default but not to the pattern is written.
- [x] Unoptimised calls and generic-file-management files (written verbatim) are unchanged.
- [x] An offset beyond the UInt16 range of `fillFileOffset` is split into several.
- [ ] Upstream merge request.
