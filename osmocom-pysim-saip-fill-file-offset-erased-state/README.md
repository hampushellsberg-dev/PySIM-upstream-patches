# pySim SAIP fill-pattern defects

Two bugs in how `pySim/esim/saip/__init__.py` decides what an EF byte the
Profile Package never writes reads back as. They are independent; the second
only becomes visible once a profile declares a fill pattern at all.

## Bug 1 -- `fillFileOffset` gaps are NUL-filled instead of erased

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Affected: `pySim/esim/saip/__init__.py`, `File.file_content_from_tuples`

`File.file_content_from_tuples` linearizes a file's data tuples through an
`io.BytesIO`:

```python
stream = io.BytesIO()
if self.fill_pattern:
    stream.write(self.expand_fill_pattern())
elif self.template and self.template.default_val:
    stream.write(self.template.expand_default_value_pattern(self.file_size))
stream.seek(0)
for k, v in l:
    ...
    elif k == 'fillFileOffset':
        stream.seek(v, os.SEEK_CUR)
    elif k == 'fillFileContent':
        stream.write(v)
```

Seeking a `BytesIO` past its end and writing makes Python fill the skipped
region with null bytes. So every byte a Profile Package skips beyond whatever
step 1 laid down comes back as `00`.

That is the wrong value. TCA "Profile interoperability technical
specification" V3.4.1 §8.3.5 defines `fillFileOffset` as a pointer move only --
it writes nothing, so the skipped bytes keep the content the file was created
with. §8.3.3 states the effect of `fillFileContent` / `fillFileOffset` is the
same as "creating a file with a fill/repeat pattern, or non-pattern content and
thereafter updating the content via Update", which is the comment already in
the function. A file created with no pattern is erased, not zeroed: §9.10 says
the default EF-ARR image is "truncated or padded with 'FF...FF' as required",
and the worked example in §9.10.3.3 encodes EF-ARR as `fillPattern 'FF'H`
followed by six `fillFileOffset` / `fillFileContent` pairs whose gaps are that
`FF` pattern.

Three cases reach the zero-fill:

1. **No pattern and no template.** A `File` built from a raw PE whose
   `templateID` does not resolve (`self.template is None`) starts from an empty
   stream, so *every* gap is NUL. This is the common case for operator profiles
   handled as a plain PE list.
2. **No pattern and a template without `default_val`.** Same empty stream.
3. **A short literal `default_val`.** `expand_default_value_pattern` returns
   `h2b(self.default_val)` unchanged when the pattern contains no `...`,
   ignoring its `length` argument. A default shorter than `file_size` leaves a
   NUL-growable tail behind it.

`file_content_to_tuples` -- the encoder in the same class -- already treats
`FF` as the implicit baseline when no template applies:

```python
sm = SequenceMatcher(a=b'\xff'*len(self.body), b=self.body)
```

so the two directions disagree about what an unwritten byte is.

### Harm

The wrong bytes do not stay in the reader. `file_content_to_tuples(optimize=True)`
re-derives the tuple list from `File.body`, so a decode/edit/encode cycle
launders each NUL gap into explicit `fillFileContent` zeros: the package grows,
and the on-card semantics of those bytes changes from "erased" to "written
zeros". For EF-ARR that turns unallocated record slots into records whose first
byte is `00`; for EF-DIR it corrupts the FF padding after the application
label.

### Fix

Fill the region the write head skips with `FF` rather than letting `BytesIO`
grow it with NUL, leaving every explicitly written byte and every byte covered
by the fill/repeat pattern or template default untouched. See
`pysim-saip-fill-file-offset-erased-state.patch`.

## Bug 2 -- a fill/repeat pattern is applied once per file, not per record

`File.expand_fill_pattern` hands the whole file size to
`ts_102_222.expand_pattern`, which has no notion of records:

```python
def expand_fill_pattern(self) -> bytes:
    return ts_102_222.expand_pattern(self.fill_pattern, self.fill_pattern_repeat, self.file_size)
```

ETSI TS 102 222 §6.3.2.2 defines both patterns record-wise. Tag `C1`:

> The first W-1 bytes of the transparent EF **or the first W-1 bytes of each
> record of a record oriented EF** shall be initialized with the first W-1
> bytes of the Filling Pattern.

and tag `C2` repeats "for all remaining blocks of X bytes of data in the file
or in a record", truncating "at the end of the file **or at the end of each
record**".

So a linear-fixed EF.EXT2 of ten 13-byte records declaring `fillPattern
'00FF'H` holds `00 FF..FF` in *every* record. pySim expands it to a single
`00` followed by 129 erased bytes:

```text
pySim   00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...
card    00FFFFFFFFFFFF 00FFFFFFFFFFFF 00FFFFFFFFFFFF...
```

Byte 1 of an extension record is its record type, and `00` means "no record".
Every record after the first is reported with a record type of `FF`, which is
not a defined value. The same applies to EF.SMS (`00` = free slot) and to any
`C2` pattern whose length does not divide the file size.

`expand_pattern` also does not truncate: for `size < len(pattern)` the
`pattern[-1:] * pad_len` term multiplies by a negative number and yields `b""`,
so the full pattern is returned and the file overflows its own size.

### Fix

Expand one record and repeat it for a record oriented EF, truncating the
pattern at the record length. See
`pysim-saip-record-aware-fill-pattern.patch`.

## Bug 3 -- a record template's default value is expanded once per file, not per record

`File.file_content_from_tuples` (step 1) and `File.file_content_to_tuples(optimize=True)`
hand the whole file size to the template:

```python
elif self.template and self.template.default_val:
    stream.write(self.template.expand_default_value_pattern(self.file_size))
...
default = self.template.expand_default_value_pattern(length=len(self.body))
```

The SAIP section 9 tables give a linear-fixed or cyclic file its default
value per record. EF ICI (V3.4.1, page 86) is 20 records of 38 bytes with the
default `FF...FF 0000000001FFFF`: one 38-byte record, its tail closing every
record. `FileTemplate._default_value_len` already returns `rec_len` for `LF` /
`CY`, so the template class knows the unit; only the two callers expand over
`file_size`. For EF ICI that puts `0000000001FFFF` at bytes 753..759 of the
file and erased bytes at the end of records 1 to 19:

```text
pySim   FF*753 0000000001FFFF
card    FF*31 0000000001FFFF  FF*31 0000000001FFFF  ... (20 records)
```

### Harm

Every record but the last reads back with an erased tail where the card holds
the default's tail, and the encoder round trip (`file_content_to_tuples(
optimize=True)`) treats a profile's per-record tails as differences from the
default and writes them out as content, growing the package by six bytes per
record and hiding what the template already provides.

### Fix

Expand one record and repeat it whenever a record oriented template is asked
for more than one record; a transparent file, a single record and a literal
default that does not fill its record are unchanged. See
`pysim-saip-record-aware-template-default.patch`.

## Files

- `pysim-saip-fill-file-offset-erased-state.patch` -- the fix for bug 1.
- `pysim-saip-record-aware-fill-pattern.patch` -- the fix for bug 2.
- `pysim-saip-record-aware-template-default.patch` -- the fix for bug 3.
- `repro_fill_file_offset_erased_state.py` -- standalone repro, no YggdraSIM
  imports. Covers all three cases above, plus the two that already behave
  correctly (`fillPattern 'FF'H` and `fillPattern '00'H`), and reproduces the
  §9.10.3.3 worked example byte for byte.
- `validation.txt` -- before/after output of the repro and of the shipped
  reference profile.

## Stress-test checklist

- [x] §9.10.3.3 EF-ARR example decodes to the six access rules of the §9.10
      table, each padded to 37 B with `FF`.
- [x] `fillPattern '00'H` (§9.10.3 example with a zero pattern) still yields
      zeros -- the fix must not convert a pattern byte.
- [x] A gap that falls *inside* the pattern or template default keeps the
      pattern byte; only the grown region changes.
- [x] `doNotCreate` still returns `None`; an unknown tuple key still raises.
- [x] Transparent, linear-fixed and cyclic files, and files reached through
      `ProfileElementGFM`.
- [x] Decode -> `file_content_to_tuples(optimize=True)` -> decode is stable
      (the gap stays a gap instead of becoming explicit `00` content).
- [x] A linear-fixed EF with a `C1` pattern opens every record with the
      pattern, not only the first.
- [x] A `C2` pattern truncates at each record boundary.
- [x] A pattern longer than the record length is truncated to it.
- [x] A single-record file expands identically under both readings.
- [x] Transparent and BER-TLV files are byte-for-byte unchanged.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py` wraps the imported class so a
stock pinned pySim behaves correctly: `install_erased_state_file_fill` for
bug 1 and `install_record_aware_fill_pattern` for bug 2. It calls upstream first, then replays the tuple list twice
-- once growing gaps with `FF`, once with `00` -- and requires upstream's own
output to equal one of the two, raising `SaipErasedStateFillMismatch`
otherwise. Matching the `FF` replay means upstream has landed this fix and the
wrapper is already a no-op; that is the signal to delete it.
The record-aware wrapper likewise calls upstream first, leaves transparent and
BER-TLV files untouched, and checks its expansion against the declared geometry
and -- for a single-record file, where both readings must coincide -- against
upstream's own bytes, raising `SaipRecordFillMismatch` otherwise.

`tests/test_saip_erased_state_file_fill.py` pins both unpatched callables
through `__wrapped__`, so they fail the day the pin moves to a fixed pySim.
