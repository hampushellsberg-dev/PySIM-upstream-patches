# pySim SAIP profile-template fixes

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Base commit: `e0a9e73267f18fed1d81874938f5e2831afd12e6`

Bugs 1 and 2 are a chain: the second only becomes reachable once the first is
fixed. Bug 3 is independent of both and is fixed by a one-line correction.

## Bug 1 -- implicit template parent path

`FsProfileElement.add_file()` assumes that every intermediate DF listed in a
`FileTemplate.ppath` has already been materialized in the sequence filesystem
tree. Some SAIP profile elements can contain a child EF under a template-defined
DF before the DF shell itself appears in the decoded field order, or without
encoding the shell explicitly.

For `FilesTelecomV2`, an `EF.PBR` entry uses `ppath=[0x5F3A]`. If the current
`DF.TELECOM` node has no `DF.PHONEBOOK` child yet, pySim raises:

```text
KeyError: 24378
```

`24378` is `0x5F3A`.

### Fix

When walking a template parent path, materialize a missing intermediate
template DF from the same profile template before adding the child file. If the
explicit DF field is decoded later, merge it into the synthesized node so
existing children remain attached.

## Bug 2 -- phonebook `EF.PBC` template row mislabeled

After the parent-path issue is fixed, the same decoded phonebook PE can fail
on `ef-pbc`:

```text
ValueError: Cannot add File(ef-pbc) of unknown file_type None to tree
```

`PE_Definitions-3.3.1.asn` contains `ef-pbc`, but the phonebook template row
for `4F60..4F67` is mislabeled as `EF.ADN`. TCA SAIP §9.4 defines that row as
`EF.PBC`, linear fixed, record length `2`, ARR `5`, default `00...00`, with
file size and SFI supplied by the instance. The local manual file tree also
maps PBR discriminator `C5` to `PBC`.

### Fix

Correct the `4F60..4F67` phonebook template row from `EF.ADN` to `EF.PBC`.

## Bug 3 -- `FilesAtMF` declares `EF.ICCID` at the wrong file identifier

`FilesAtMF` in `pySim/esim/saip/templates.py` declares EF.ICCID at file
identifier `0x2F02`:

```python
FileTemplate(0x2f02, 'EF.ICCID',     'TR', None,   10,  11, None, None, True),
```

ETSI TS 102 221 §13.2 Table 13.1 assigns EF_ICCID the file identifier `2FE2`.
`2F02` is not allocated to any file at MF level. The remaining template fields
are correct: transparent, 10 bytes, ARR record 11, no SFI.

The value looks like a transposition of `2FE2`. pySim itself carries the
correct identifier elsewhere -- `pySim/legacy/ts_51_011.py` maps
`'ICCID': '2FE2'` -- so the SAIP MF template is the only place in the library
that disagrees.

Nothing raises, so the wrong identifier is silently carried into every
consumer that resolves files by FID: filesystem trees, path-keyed diffs, and
anything comparing a decoded profile against a vendor's profile-definition
document. The FID also participates in the file's path, so the file is
reported at `3F00/2F02` instead of `3F00/2FE2`.

### Fix

Correct the `FilesAtMF` row from `0x2f02` to `0x2fe2`. No other field changes.

## Patches

| Patch | Bug | File |
|-------|-----|------|
| `pysim-saip-implicit-template-ppath.patch` | 1 | `pySim/esim/saip/__init__.py` |
| `pysim-saip-phonebook-pbc-template.patch` | 2 | `pySim/esim/saip/templates.py` |
| `pysim-saip-mf-iccid-fid.patch` | 3 | `pySim/esim/saip/templates.py` |

## Reproduction

Bugs 1 and 2:

```bash
python upstream_patches/osmocom-pysim-saip-implicit-template-ppath/repro_saip_implicit_template_ppath.py
```

Before the patches, the script fails with `KeyError: 24378`.

With only the parent-path patch applied, the script fails with:

```text
ValueError: Cannot add File(ef-pbc) of unknown file_type None to tree
```

After both patches, it prints:

```text
3F00/7F10/5F3A/4F30
3F00/7F10/5F3A/4F09
```

Bug 3:

```bash
python upstream_patches/osmocom-pysim-saip-implicit-template-ppath/repro_saip_mf_iccid_fid.py
```

Before the patch the script prints `EF.ICCID fid=2F02` and exits non-zero.
After the patch it prints `EF.ICCID fid=2FE2` and exits zero.

Both repro scripts honour `YGGDRASIM_REPRO_PYSIM_ROOT` to run against a
temporary pySim copy instead of the workspace checkout.

## Validation Checklist

- Minimal reproduction fails before the patch with `KeyError: 24378`.
- Minimal reproduction passes after the patch and resolves `EF.PBR` below
  `3F00/7F10/5F3A`.
- Minimal reproduction fails with `ValueError: Cannot add File(ef-pbc) of
  unknown file_type None to tree` if the parent-path fix is present without the
  `EF.PBC` template correction.
- Minimal reproduction passes after both patches and resolves `EF.PBC` below
  `3F00/7F10/5F3A`.
- `EF.ICCID` reproduction reports `2F02` before the third patch and `2FE2`
  after; `EF.ICCID` then resolves at `3F00/2FE2` in a decoded profile's file
  tree.
- The corrected identifier agrees with `pySim/legacy/ts_51_011.py`; `0x2f02`
  appears nowhere else in the library.
- Every patch applies to the base commit above with `git apply`.
- Parse changed Python files with `ast.parse`.
- Check upstream patch whitespace with `git diff --check`.
