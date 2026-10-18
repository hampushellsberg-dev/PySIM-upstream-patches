# pySim SAIP: a GFM that creates the MF cannot be decoded

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Base commit: `e0a9e73267f18fed1d81874938f5e2831afd12e6`
Affected: `pySim/esim/saip/__init__.py`, `ProfileElementGFM.add_file`,
`ProfileElementGFM.pe2files` (through `ProfileElementSequence.cd`)

## Bug

TCA "Profile interoperability technical specification" V3.4.1 orders the
profile elements in §8.1:

> PE-MF: May be provided once as the first element of the file system
> creation after the "ProfileHeader" in a Full Profile. If this PE is not
> used, the MF shall be created as the first element of the file system
> using the "PE-GenericFileManagement" in a Full Profile. PE-MF is not
> allowed in the IoT Minimal Profile.

§7.5 repeats that an IoT Minimal Profile Package uses PE-IoT and
PE-GenericFileManagement and that PE-MF is not allowed, and §8.3.5 states the
usage rule of the GFM PE: "It shall be the first element of the file system
creation in case it is used to create the MF instead of using PE-MF."

Such a profile starts with `header, genericFileManagement (createFCP 3F00,
createFCP 2F06, ...)`. pySim's `ProfileElementGFM.pe2files` runs on decode
(`_post_decode`) and, for every file, calls `add_file`, which resolves the
parent through the sequence's MF:

```python
if hasattr(self.pe_sequence, 'mf'):
    if isinstance(path, Path):
        parent = self.pe_sequence.mf.lookup_by_path(Path(path[:-1]))
    else:
        parent = self.pe_sequence.mf.lookup_by_fidpath(path[:-1])
```

`ProfileElementSequence.mf` is `None` until a PE-MF was decoded, so the
createFCP that *is* the MF raises

```text
AttributeError: 'NoneType' object has no attribute 'lookup_by_fidpath'
```

and `ProfileElementSequence.from_der` fails for the whole package. The same
dereference sits in `ProfileElementSequence.cd` (`df = self.mf` followed by
`df.children`), which `pe2files` calls before each file once a `filePath`
below the MF is selected.

The decoded ASN.1 is fine; only the convenience file-system model cannot be
built. Every profile that follows the §8.1 GFM route -- IoT Minimal
Profiles by definition, and the Full Profiles of vendors that emit the file
system as GFM commands -- fails to open.

## Fix

`pysim-saip-gfm-mf-creation.patch`:

- `ProfileElementGFM.add_file`: while the sequence has no MF, the file with
  identifier `3F00` and file type `DF` becomes the `FsNodeMF` root
  (`sequence.mf` and `sequence.cur_df`), the same way
  `FsProfileElement.add_file` roots a PE-MF `mf` entry. Any other file that
  reaches a rootless sequence is registered by path without a tree node, as
  the method already does for a PE decoded outside a sequence.
- `ProfileElementSequence.cd`: a rootless sequence selects nothing
  (`cur_df = None`) instead of dereferencing `None`.

The file identifier `3F00` is the MF per ETSI TS 102 221; the GFM walker in
`pe2files` starts at `[0x3f00]`, so the MF's own path is `3F00/3F00` and its
`pe_name` keeps that value.

## Repro

`repro_saip_gfm_mf_creation.py` builds `header + GFM(createFCP 3F00,
createFCP 2F06, fillFileContent) + end` with pySim's own encoder and parses
it with `ProfileElementSequence.from_der`; `--compensated` first installs
the YggdraSIM-side compensation (`install_gfm_mf_creation`).
`validation.txt` holds both outputs.

The synthetic profile carries no operator identifiers (ICCID from the ITU-T
E.118 test range). The report originated from a vendor IoT profile whose
first PE after the header is a GFM creating `3F00`, `2F06`, `2F05`, `2FE2`
and `2F00`.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_gfm_mf_creation`,
installed by `ensure_workspace_pysim_on_path` for the GUI, the TUI and the
CLI. It wraps `ProfileElementGFM.add_file` and `ProfileElementSequence.cd`
with the same two rules, verifies that the created MF is the sequence root
and fails closed (`SaipGfmMfCreationMismatch`) when it is not.
`tests/test_saip_pysim_compat.py::GfmMfCreationTests::test_upstream_still_needs_the_gfm_mf_compensation`
calls the unwrapped upstream method and expects the `AttributeError`, so the
compensation cannot outlive the upstream fix unnoticed: when that test
fails, delete the installer and this folder.

## Stress-test checklist

- [x] `header + GFM(MF, EF.ARR) + end` decodes; `sequence.mf` is an
      `FsNodeMF`, `2F06` is its child, the PE re-encodes byte for byte.
- [x] `header + GFM(filePath 7F20, createFCP 2F06) + end` (no MF anywhere)
      decodes; the file is reachable as `3F00/7F20/2F06`, no node.
- [x] A PE-MF profile (`header, mf, ...`) is unaffected: the wrapper
      delegates whenever the sequence already has a root.
- [x] Installing twice is a no-op (`install_gfm_mf_creation()` returns
      `False` the second time).
- [x] A vendor IoT profile (GFM-first, ten PEs) opens in the SAIP workbench
      with a complete strict parse.
- [x] `pysim/` checkout present and parked: the installed package and the
      fork carry the same `add_file`, both are patched at runtime.
