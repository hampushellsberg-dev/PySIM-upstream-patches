# pySim has no SGP.22 v3 RSP module

`pySim/esim/rsp.py` compiles one `RSPDefinitions` module,
`pySim/esim/asn1/rsp/rsp.asn`, which declares itself `version-two(2)`. SGP.22
v3.1 publishes its own module in Annex H (`asn1modules(1) sgp22v3(3)`, pages
437-462 of the v3.1 text). Compared type by type (`v2-vs-v3.1-types.txt`), v3.1
has 219 assignments against pySim's 149: 91 added, 21 removed or renamed, 59
changed.

## What goes wrong

- None of the twenty-two BF-tagged request and response types v3.1 added can
  be encoded or decoded (ES10: sections 5.7.3, 5.7.23-5.7.29; ES9+: 5.6.6,
  5.6.7; ES11: 5.8.3): `EuiccConfiguredData`, `LoadRpmPackage`,
  `VerifySmdsResponse`, `CheckEvent`, `AlertData`, `PrepareDeviceChange`,
  `VerifyDeviceChange`, `ConfirmDeviceChange`, `VerifySmdpResponse`,
  `CheckProgress`, `VerifyProfileRecovery`, `DeleteNotificationForDc`. The same
  holds for the v3 ES9+ / ES11 types (`AuthenticateClientOkRpm`,
  `AuthenticateClientOkDeviceChange`, `EventRecordV3`, ...).
- Members v3.1 added to existing types are skipped without an error on decode
  (the module is `EXTENSIBILITY IMPLIED`) and dropped without an error on
  encode: `ServerSigned1.sessionContext`, `AuthenticateResponseOk.otherCertsInChain`,
  `ProfileInfo.enabledOnEsimPort`, `EnableProfileRequest.targetEsimPort`, ...

```
pySim.esim.rsp.asn1_v3: absent
  MISSING EuiccConfiguredDataRequest     (BF tag 3C)
  ...
FAIL: 22 of 22 BF-tagged SGP.22 v3.1 types unavailable.
```

## Why a second module and not an update of rsp.asn

Merging v3.1 into the v2 file cannot be done faithfully, and it would break
the callers:

- **Same bytes, different meaning.** `DeviceCapabilities` is positionally
  tagged. Tag `88` is `rspRpmSupportedVersion` in pySim's v2 module and
  `nrEpcSupportedRelease` in v3.1; one module cannot name it both ways.
- **Stricter types.** v3.1 makes `ProfileInstallationResultData.smdpOid`
  mandatory; the v2 module has it OPTIONAL. A v3.1 decoder rejects a v2
  eUICC's installation result without it (`MissingMandatoryFieldError`).
- **Renames.** `svn` -> `lowestSvn`, `simaResponse` -> `ppiResponse`,
  `eumCertificate` -> `nextCertInChain`, `RspCapability` -> `EuiccRspCapability`,
  enumeration names (`notificationEnable` -> `notificationLocalEnable`, ...).
  osmo-smdpp reads `eumCertificate` in two places, `contrib/es9p_client.py`
  builds requests with seven v2 member names.
- **Removed types.** `LoadCRL*` (SGP.22 v3.1 section 5.7.12: "no longer supported
  by the eUICC"), `EuiccConfiguredAddresses*`, `PprIds.ppr3`.
- **SGP.32 builds on v2.** The SGP.32 v1.3 ASN.1 module imports `RspCapability`,
  `EuiccSignPIR` and `UICCCapability` from `RSPDefinitions {... sgp22v2(2)}`;
  v3.1 has none of the three, so an SGP.32 compile needs the v2 module to stay.

So the v2 module stays the default (`rsp.asn1`) and v3.1 sits next to it; a
caller picks the module that matches the SGP.22 version its peer declared.
`EUICCInfo1` / `EUICCInfo2`, which are read before that version is known, are
handled in the v2 module by `osmocom-pysim-rsp-v3-euiccinfo/`.

## The patch

`pysim-rsp-v3-module.patch` (apply after `pysim-rsp-v3-euiccinfo.patch`):

- `pySim/esim/asn1/rsp_v3/rsp.asn`: SGP.22 v3.1 Annex H, transcribed from the
  published text by `transcribe_annex_h.py`. Comments the PDF wrapped onto a
  second line are rejoined; the definitions are unchanged except one.
- `pySim/esim/__init__.py`: `compile_asn1_paths()`, which compiles named files
  and subdirectories below `asn1/`. The v3.1 module imports `UICCCapability`
  from the SAIP `PEDefinitions` and needs the two PKIX modules from `rsp/`, and
  `compile_asn1_subdir()` reads one subdirectory only.
- `pySim/esim/rsp.py`: `asn1_v3()`, compiled on first call and cached. The
  compile takes about 0.44 s against 0.23 s for the v2 module, which every
  `import pySim.esim.rsp` already pays; callers that never use v3 pay nothing.
- `setup.py`: `asn1/rsp_v3/*.asn` in `package_data`. Without it the wheel
  silently lacks the file; no test run from a checkout would notice.
- `tests/unittests/test_esim_rsp.py` (extends the file `pysim-rsp-v3-euiccinfo.patch`
  creates, so this patch does not apply without that one): all twenty-two BF-tagged v3.1 types round-trip
  under their tags; the tag `88` and `smdpOid` differences; `ServerSigned1` and
  `CtxParamsForCommonAuthentication` encode byte-for-byte the same under both
  modules; the v3 member names.

### The one deviation from the published module

Annex H declares `OPENTYPE ::= CLASS { &typeId OBJECT IDENTIFIER, &Type }` and
types `VendorSpecificExtension` with `OPENTYPE.&typeId` / `OPENTYPE.&Type`.
asn1tools cannot resolve an information object class, so the two fields are
`OBJECT IDENTIFIER` and `ANY`, which encode the same on the wire; the class is
kept as a comment. The v2 module on the fork already does the same since
`osmocom-pysim-rsp-v3-metadata/`.

### How the transcription was checked

The PDF text sets some code at column 0 (the published `AuthenticateErrorCode`
lists `missingCrl(9)` .. `invalidIccid(14)` there), so "a column-0 line after a
comment is wrapped comment text" is not safe on its own. All 157 such lines
were reviewed: 148 are comment text, three are comment lines of their own,
six are named numbers. The script prints the nine it keeps. The result:

- compiles (195 types in `RSPDefinitions`), ASCII only, no line with two `--`
  markers (a second `--` ends an ASN.1 comment, and asn1tools parses the rest
  of the line as code);
- token-for-token equal to a comment-free extraction of the same pages, apart
  from the OPENTYPE substitution and the six `AuthenticateErrorCode` numbers
  that extraction had lost;
- regenerated byte-for-byte by `transcribe_annex_h.py`, which takes the library
  slug, so a later SGP.22 version only needs its pages.

Not in this change: v3 behaviour in osmo-smdpp (otherCertsInChain, RPM, Device
Change, ...), pySim-shell commands for the new ES10 functions, and a policy for
choosing the module from the peer's version.

Commit subject on the fork:
`esim/asn1: add the SGP.22 v3.1 RSPDefinitions module as rsp_v3`

On hampushellsberg-dev/pysim as `3fd51ec` (2026-10-29), after `d5b3266`. Compared
with the first version of this patch, `compile_asn1_paths()` reads the module
text as UTF-8; `read_text()` without an encoding uses the locale's.

## Validation

`validation.txt`: the transcription and its acceptance checks; the repro before
and after; every `tests/unittests` file, unpatched and with both patches
(identical apart from the new `test_esim_rsp.py`); the wheel built from the
patched tree lists `rsp_v3/rsp.asn` and `asn1_v3()` works when imported from
the unpacked wheel; both patches applied in order to a fresh clone reproduce
the tested tree.

`check_against_pdf.py` compares the module with an independent `pdftotext`
extraction of the same pages, code and full text; the only differences are the
OPENTYPE replacement and the transcription notes (`validation.txt`).

The tests use OIDs with first arc 1. With the asn1tools YggdraSIM pins, an OID
with first arc 2 (the SGP.26 test SM-DP+ OIDs are `2.999.x`) decodes wrongly
(`2.999.10` comes back as `26.39.10`); that is `eerimoq-asn1tools-oid-arc2/`,
not this module.

## The YggdraSIM-side half

YggdraSIM pins hampushellsberg-dev/pysim; the module reaches it as a fork commit
plus a pin move. `Tools/Asn1TlvDecode/gsma_schema.py` takes `asn1_v3()` as a
second specification for the type names its SGP.22 v2 + SGP.32 compile lacks,
so the context decoder resolves the twenty-two types above; with a pySim
without `asn1_v3` it behaves as before.

## Stress-test checklist

- [x] Every BF-tagged v3.1 type round-trips encode -> decode under its SGP.22 v3.1 tag.
- [x] Tag `88` of `DeviceCapabilities` decodes per module; `smdpOid` absence is rejected by v3.1 only.
- [x] Types v3.1 did not change encode byte-for-byte the same under both modules.
- [x] The v2 module and every existing `tests/unittests` result are unchanged.
- [x] The wheel carries `rsp_v3/rsp.asn`; the module loads from an installed layout.
- [ ] Decoding captures from a v3 eUICC and a v3 SM-DP+ (lab).
