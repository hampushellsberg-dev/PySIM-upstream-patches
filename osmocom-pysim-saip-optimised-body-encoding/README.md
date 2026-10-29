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

Retired on 2026-10-23: YggdraSIM pins hampushellsberg-dev/pysim, upstream master with this fix on top, and no longer carries what this section describes. The one gap the pinned pySim still had, offsets beyond UInt16, is fixed below.

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

## An offset beyond UInt16

TCA SAIP V3.4.1 §8.3.2 types `fillFileOffset` as UInt16, and §8.3.5 moves the
pointer from where it stands, so a longer move is the same move made in
several steps. With `0001-...` applied (hampushellsberg-dev/pysim `f2db3ab`),
`file_content_to_tuples(optimize=True)` still emits a gap as one offset: one
changed byte at offset 66000 of a 70000-byte transparent file encodes as

```
offsets: [66000] | content bytes: 4000 | rebuilds: True
```

an INTEGER outside the type, which the DER encoder writes without complaint.
(The 4000 content bytes are the changed byte and the 'FF' tail behind it:
`SequenceMatcher` treats the frequent 'FF' byte as junk and finds no match
after the difference. That costs size, not correctness.)

`0002-saip-split-fill-file-offset-beyond-uint16.patch`, against `f2db3ab`,
makes the move in steps of at most 0xFFFF:

```
offsets: [65535, 465] | content bytes: 4000 | rebuilds: True
```

YggdraSIM side: `install_fill_file_offset_split` in
`Tools/ProfilePackage/saip_pysim_compat.py` splits the offsets pySim returns,
checks that every `fillFileContent` still lands where pySim put it, and is a
no-op once pySim splits them itself;
`tests/test_saip_pysim_compat.py::BodyEncodingAgainstCreationContentTests`
pins the gap (`test_upstream_still_emits_an_offset_beyond_uint16`).

The YggdraSIM compensation retired on 2026-10-23 split the offset too, but only
on its own path: it replaced pySim's encoding when that did not rebuild the
body, which the pinned pySim now always does.

On hampushellsberg-dev/pysim as `7723a45` (2026-10-29, `esim.saip: split a
fillFileOffset beyond the range of UInt16`), with
`FileContentTest.test_fill_file_offset_fits_uint16` in
`tests/unittests/test_esim_saip.py`; `validation.txt` has the runs.
