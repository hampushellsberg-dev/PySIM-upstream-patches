# pySim, simtrace2 and asn1tools fixes

Defects found in osmocom pySim, the osmocom SIMtrace2 firmware and asn1tools
while building YggdraSIM. The fixed code is in forks, one commit per fix on
top of the upstream branch, in an order that applies and tests cleanly:

| Project | Fork, branch | On top of | Commits | Tip |
|---|---|---|---|---|
| pySim | [hampushellsberg-dev/pysim](https://github.com/hampushellsberg-dev/pysim), `master` | osmocom/pysim `master` at `9aa8934` | 24 | `3322531` |
| simtrace2 | [hampushellsberg-dev/simtrace2](https://github.com/hampushellsberg-dev/simtrace2), `master` | osmocom/simtrace2 `master` at `9467005` | 1 | `697db3b` |
| asn1tools | [hampushellsberg-dev/asn1tools-loop-fix](https://github.com/hampushellsberg-dev/asn1tools-loop-fix), `master` | osmocom/asn1tools `master` at `44277cd` | 2 | `c204026` |
| asn1tools | same fork, `fix-unbounded-loops` | eerimoq/asn1tools 0.167.0 at `7b72219` | 1 | `1d0c56f` |

Fetching a series, for example pySim:

    git fetch https://github.com/hampushellsberg-dev/pysim.git master
    git log --reverse --oneline 9aa8934..FETCH_HEAD

Each folder in this repository holds the analysis of one defect: a README
with the cause and the fix, the patch file(s), and where one exists a repro
script with its before and after output in `validation.txt`. The folders say
why; the forks carry the code.

## pySim

Applied in this order; a later commit can rely on an earlier one (the GFM
that creates the MF before the IoT profile elements, the proprietaryEFInfo
fix before the optimised body encoding).

| # | Commit | Subject | Folder |
|---|---|---|---|
| 1 | `8e68071` | esim.saip: create a template DF missing from a file's parent path | [osmocom-pysim-saip-implicit-template-ppath](osmocom-pysim-saip-implicit-template-ppath/) |
| 2 | `f550c53` | esim.saip: the 4F60..4F67 phonebook template rows are EF.PBC | [osmocom-pysim-saip-implicit-template-ppath](osmocom-pysim-saip-implicit-template-ppath/) |
| 3 | `5aa58f5` | esim.saip: FilesAtMF lists EF.ICCID at 2FE2 | [osmocom-pysim-saip-implicit-template-ppath](osmocom-pysim-saip-implicit-template-ppath/) |
| 4 | `4916ee8` | esim/asn1/rsp: add the SGP.22 v3 members of StoreMetadataRequest | [osmocom-pysim-rsp-v3-metadata](osmocom-pysim-rsp-v3-metadata/) |
| 5 | `a22f91e` | esim.saip: a fillFileOffset gap reads back as 'FF', not NUL | [osmocom-pysim-saip-fill-file-offset-erased-state](osmocom-pysim-saip-fill-file-offset-erased-state/) |
| 6 | `cd72b0a` | esim.saip: expand a fill or repeat pattern per record | [osmocom-pysim-saip-fill-file-offset-erased-state](osmocom-pysim-saip-fill-file-offset-erased-state/) |
| 7 | `a209bf3` | ts_102_221: decode the termination state of the life cycle status | [osmocom-pysim-lcsi-termination](osmocom-pysim-lcsi-termination/) |
| 8 | `5143702` | setup: make smpp.twisted3 an extra, only pySim-smpp2sim.py needs it | [osmocom-pysim-smpp-twisted-optional](osmocom-pysim-smpp-twisted-optional/) |
| 9 | `3965ff1` | esim.saip: let a GenericFileManagement PE create the MF | [osmocom-pysim-saip-gfm-mf-creation](osmocom-pysim-saip-gfm-mf-creation/) |
| 10 | `32ba902` | personalization: SmspTpScAddr edits record 1 of EF.SMSP only | osmocom-pysim-saip-record-count (companion, see below) |
| 11 | `0061613` | esim.saip: derive nb_rec from efFileSize when the descriptor omits it | [osmocom-pysim-saip-record-count](osmocom-pysim-saip-record-count/) |
| 12 | `58bafd4` | esim.saip: map cdmaParameter, nonStandard, iot and opt-iot to classes | [osmocom-pysim-saip-extra-profile-elements](osmocom-pysim-saip-extra-profile-elements/) |
| 13 | `2f9017e` | esim.saip: a ranged template file resolves to the start of its range | [osmocom-pysim-saip-template-range-fid](osmocom-pysim-saip-template-range-fid/) |
| 14 | `82c4b11` | esim.saip: expand a record template's default value per record | [osmocom-pysim-saip-fill-file-offset-erased-state](osmocom-pysim-saip-fill-file-offset-erased-state/) |
| 15 | `b7c4e42` | esim.saip: apply proprietaryEFInfo when the Fcp has no fileDescriptor | [osmocom-pysim-saip-proprietary-efinfo-without-descriptor](osmocom-pysim-saip-proprietary-efinfo-without-descriptor/) |
| 16 | `393b507` | esim.saip: encode an optimised body against the creation content | [osmocom-pysim-saip-optimised-body-encoding](osmocom-pysim-saip-optimised-body-encoding/) |
| 17 | `f2db3ab` | esim.saip: the keyList of a PE-SecurityDomain is optional | [osmocom-pysim-saip-sd-optional-key-list](osmocom-pysim-saip-sd-optional-key-list/) |
| 18 | `d5b3266` | esim/asn1/rsp: decode the SGP.22 v3 members of EUICCInfo1 and EUICCInfo2 | [osmocom-pysim-rsp-v3-euiccinfo](osmocom-pysim-rsp-v3-euiccinfo/) |
| 19 | `3fd51ec` | esim/asn1: add the SGP.22 v3.1 RSPDefinitions module as rsp_v3 | [osmocom-pysim-rsp-v3-module](osmocom-pysim-rsp-v3-module/) |
| 20 | `adf97af` | esim/asn1/rsp: add OperatorId as an alias of OperatorID | [osmocom-pysim-rsp-operatorid](osmocom-pysim-rsp-operatorid/) |
| 21 | `74f5002` | log: print a record only once when loggers are nested | [osmocom-pysim-log-duplicate-handlers](osmocom-pysim-log-duplicate-handlers/) |
| 22 | `7723a45` | esim.saip: split a fillFileOffset beyond the range of UInt16 | [osmocom-pysim-saip-optimised-body-encoding](osmocom-pysim-saip-optimised-body-encoding/) |
| 23 | `1460a87` | esim.saip: keep keyAccess and keyCounterValue of security domain keys | [osmocom-pysim-saip-sd-key-access-counter](osmocom-pysim-saip-sd-key-access-counter/) |
| 24 | `3322531` | esim.saip: fix decoding of rfu PEs with an empty body | [osmocom-pysim-saip-empty-pe-body](osmocom-pysim-saip-empty-pe-body/) |

Commit 10 has no folder of its own. `SmspTpScAddr` in
`pySim/esim/saip/personalization.py` has read EF.SMSP as a single record
since it was added. The TS.48 v5 profiles in `smdpp-data/upp` declare two
records of 42 bytes (`efFileSize` 84), so once commit 11
takes the record count from `efFileSize`, decoding the whole body as one
record fails and `test_configurable_parameters` fails with it. Its patch
file sits in `osmocom-pysim-saip-record-count/`.

Checked at every commit: the tree compiles, `test_esim_saip`, `test_files`,
`test_esim`, `test_euicc`, `test_tlvs`, `test_utils` and
`test_configurable_parameters` pass, and each folder's repro passes from the
commit that completes its fix. On the last commit every file in
`tests/unittests` gives the result it gives on `9aa8934`, plus the
added test vectors.

Commits 18-24 (2026-10-29) were checked file by file over all of
`tests/unittests` at each commit: only `test_log` (a colour-code assertion)
and `test_smpp_ota_tool` (needs smpplib) fail, as they do on `f2db3ab`. Each
of them adds a test that fails without its fix, and each folder's repro passes
from its commit on.

## simtrace2

| Commit | Subject | Folder |
|---|---|---|
| `697db3b` | host_communication: send a ZLP after any message of whole packets | [osmocom-simtrace2-cardem-zlp](osmocom-simtrace2-cardem-zlp/) |

The firmware built from this tree runs on a SIMtrace2 board in card
emulation; `validation.txt` in the folder has the before and after.

## asn1tools

| Commit | Subject | Folder |
|---|---|---|
| `46b7dc2` | codecs: fix two unbounded-loop hangs | [osmocom-asn1tools](osmocom-asn1tools/) |
| `c204026` | ber: decode an OBJECT IDENTIFIER under arc 2 past 2.39 | [eerimoq-asn1tools-oid-arc2](eerimoq-asn1tools-oid-arc2/) |
| `1d0c56f` (`fix-unbounded-loops`) | codecs: fix two unbounded-loop hangs | [eerimoq-asn1tools](eerimoq-asn1tools/) |

`master` is osmocom/asn1tools, the fork pySim's `requirements.txt`
installs, with the fixes on top; `fix-unbounded-loops` carries the loop fix
and its tests against the eerimoq upstream.
