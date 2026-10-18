# pySim SAIP template: a ranged file resolves to the last FID of its range

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Base commit: `c50f4b4a0222a964710ce3124a66fe13c804be65` (the YggdraSIM pin)

## Bug

`pySim/esim/saip/templates.py` lists a file that the SAIP templates define
with a File ID range once per FID, all rows sharing one `pe_name`:

```python
for i in range(0x58, 0x60):
    df_pb_files.append(FileTemplate(0x4f00+i, 'EF.ADN', 'LF', None, None,  5, None, 'FF...FF', False, ['nb_rec','size','sfi'], ppath=[0x5f3a]))
```

`ProfileTemplate.__init_subclass__` then fills `files_by_pename` by plain
assignment:

```python
            cls.files_by_pename[f.pe_name] = f
```

so the last row of every range wins. `FsProfileElement.pe2files()` resolves
a decoded `File` through that index, and `File.from_template()` copies the
FID, so a PE-PHONEBOOK whose `ef-adn` carries no explicit `fileID` reports
EF.ADN at `4F5F`, EF.PBC at `4F67`, EF.UID at `4F8F`, EF.EXT1 at `4F3F` and
EF.CCP1 at `4F9F`.

TCA "Profile interoperability technical specification" V3.4.1 section 9.1
(templates rules and usage, FID column):

> In case of File ID ranges the File ID of the first instance is set to the
> start value of the range. All subsequent file instances shall be created
> according to the processing defined in Figure 2.

The eUICC therefore creates the first EF.ADN at `4F58` and the first EF.PBC at
`4F60`, and an operator profile's own EF.PBR record agrees: its type 1 tags
point at ADN `4F58`, PBC `4F60`, UID `4F88`, EXT1 `4F38` and CCP1 `4F98`.
Nothing raises; the wrong FID is carried into every consumer that resolves a
template file by FID (filesystem trees, path-keyed diffs, name lookups) and
into `File.fid` itself. The encoded package is unaffected because
`File.to_fileDescriptor()` omits `fileID` when it equals the template's, which
is exactly why the mismatch stays invisible until a tree is drawn.

Across the 22 templates registered at the base commit, 41 `(template, pe_name)`
pairs resolve to a FID that is not the start of their range.

## Fix

Keep the first row listed for a `pe_name`, which is the start of the range in
every template table:

```python
            cls.files_by_pename.setdefault(f.pe_name, f)
```

`pysim-saip-template-range-start-fid.patch` carries the change.

## Reproduction

```bash
python upstream_patches/osmocom-pysim-saip-template-range-fid/repro_saip_template_range_fid.py
```

The script prints the FID `files_by_pename` resolves for each ranged
DF.PHONEBOOK file next to the start of its range and exits non-zero on the
first mismatch. It honours `YGGDRASIM_REPRO_PYSIM_ROOT` to run against a
temporary pySim copy instead of the workspace checkout, and
`YGGDRASIM_REPRO_SKIP_COMPAT=1` keeps the YggdraSIM compensation out of the
run so the upstream behaviour shows.

Before the patch (stock pin, `ef-pbc` absent because of the EF.PBC labelling
bug logged in `osmocom-pysim-saip-implicit-template-ppath/`):

```text
ef-adn   resolves 4F67  range start 4F58  MISMATCH
ef-pbc   absent from files_by_pename
ef-uid   resolves 4F8F  range start 4F88  MISMATCH
ef-ext1  resolves 4F3F  range start 4F38  MISMATCH
ef-ccp1  resolves 4F9F  range start 4F98  MISMATCH
ef-anr   resolves 4F6F  range start 4F68  MISMATCH
ef-grp   resolves 4F97  range start 4F90  MISMATCH
```

After the patch, with the EF.PBC labelling patch from the sibling folder
applied as well:

```text
ef-adn   resolves 4F58  range start 4F58  ok
ef-pbc   resolves 4F60  range start 4F60  ok
ef-uid   resolves 4F88  range start 4F88  ok
ef-ext1  resolves 4F38  range start 4F38  ok
ef-ccp1  resolves 4F98  range start 4F98  ok
ef-anr   resolves 4F68  range start 4F68  ok
ef-grp   resolves 4F90  range start 4F90  ok
```

`validation.txt` holds the captured runs.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_template_range_start_fids`
rebuilds `files_by_pename` first-listed-wins on every registered template at
import time and verifies the result against the lowest FID of each name,
raising `SaipTemplateRangeFidMismatch` when a template lists a range in
another order. It is a no-op once upstream keeps the first row, and
`tests/test_saip_phonebook_template_tree.py` pins both the outcome and the
idempotence.

## Validation Checklist

- Minimal reproduction reports `ef-adn` at `4F67` before the patch and exits
  non-zero.
- Minimal reproduction resolves every ranged DF.PHONEBOOK file to the start
  of its range after the patch and exits zero.
- The patch applies to the base commit with `git apply` / `patch -p1`.
- Parse the changed Python file with `ast.parse`.
- `tests/test_saip_phonebook_template_tree.py` passes with the workspace
  checkout present and with it parked (stock pin plus the compensation).
