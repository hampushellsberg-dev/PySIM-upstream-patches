# pySim RSP schema: EUICCInfo1/2 drop their SGP.22 v3 members

`pySim/esim/asn1/rsp/rsp.asn` is the SGP.22 v2 module. Its `EUICCInfo1` stops
at `euiccCiPKIdListForSigning [10]` and its `EUICCInfo2` at
`certificationDataObject [12]`. SGP.22 v3.1 Annex H adds three members to the
first and eight to the second.

## What goes wrong

The module is `EXTENSIBILITY IMPLIED`, so `asn1tools` skips a member it does
not know instead of rejecting the encoding. Decoding what a v3 eUICC returns
succeeds and silently loses the v3 part:

```
EUICCInfo1: 91 bytes in, 56 bytes re-encoded
  DROPPED euiccCiPKIdListForSigningV3
  DROPPED euiccRspCapability
  DROPPED highestSvn
...
FAIL: 11 members dropped without an error
```

The visible consequence is in osmo-smdpp: `InitiateAuthentication` decodes
`euiccInfo1` and adds `euiccCiPKIdListForSigningV3` to the list of CI keys it
can sign with -- if the key is present. With this schema it never is, so that
branch is dead and an eUICC whose matching CI key is listed only in the v3 list
(chains of Variant Ov3, A, B or C) gets status 8.8.2 / 3.1 ("None of the
proposed Public Key Identifiers is supported by the SM-DP+") instead of a
session.

These two types differ from every other SGP.22 v3 change: the LPA and the SM-DP+
read them *before* they know which SGP.22 version the eUICC speaks (`svn` /
`lowestSvn` and `highestSvn` are inside them). Version-specific decoding cannot
help here, so the v2 module itself has to carry the v3 members.

## Repro

```
python repro_rsp_v3_euiccinfo.py
```

Decodes an EUICCInfo1 and an EUICCInfo2 built by hand the way SGP.22 v3.1
Annex H lays them out. Exits 1 and lists the dropped members against an
unpatched pySim, exits 0 once the patch is applied.

## The patch

`pysim-rsp-v3-euiccinfo.patch` adds, transcribed from SGP.22 v3.1 Annex H:

| Type | Member | Tag |
|---|---|---|
| `EUICCInfo1` | `euiccCiPKIdListForSigningV3 [17]` | `B1` |
| `EUICCInfo1` | `euiccRspCapability [8]` | `88` |
| `EUICCInfo1` | `highestSvn [19]` | `93` |
| `EUICCInfo2` | `treProperties [13]` | `8D` |
| `EUICCInfo2` | `treProductReference [14]` | `8E` |
| `EUICCInfo2` | `additionalProfilePackageVersions [15]` | `AF` |
| `EUICCInfo2` | `lpaMode [16]` | `90` |
| `EUICCInfo2` | `euiccCiPKIdListForSigningV3 [17]` | `B1` |
| `EUICCInfo2` | `additionalEuiccInfo [18]` | `92` |
| `EUICCInfo2` | `highestSvn [19]` | `93` |
| `EUICCInfo2` | `iotSpecificInfo [20]` | `B4` |

plus the two types they reference, `LpaMode` and `IoTSpecificInfo` (an empty
SEQUENCE in SGP.22 v3.1, "reserved for SGP.32"). Every added member is
OPTIONAL with its own context tag, none of which v2 uses in these types, so a
v2 encoding is byte-for-byte unchanged (pinned by
`test_euicc_info1_v2_encoding_unchanged`).

Deliberate choices, all to keep the change purely additive:

- The v2 member names stay (`svn`, `profileVersion`, `rspCapability`, ...).
  SGP.22 v3.1 renames them (`lowestSvn`, `baseProfilePackageVersion`,
  `euiccRspCapability`, ...); renaming would break every caller that reads them.
- `EUICCInfo1.euiccRspCapability [8]` references the v2 `RspCapability`
  instead of v3's `EuiccRspCapability`. The v3 named bits (up to
  `pushServiceRegistrationSupport (24)`) are not added: asn1tools returns a BIT
  STRING as raw bytes and a bit count either way, so the names would change no
  decoded value.
- `certificationDataObject [12]` stays OPTIONAL although v3 makes it mandatory
  (`#MandatoryFromV3.0.0#`), since v2 eUICCs omit it.
- `IoTSpecificInfo` is the empty SEQUENCE SGP.22 v3.1 reserves for SGP.32.
  SGP.32 v1.3 declares its own `EUICCInfo2`, with `ipaMode [16]` where SGP.22
  has `lpaMode [16]`, and fills `IoTSpecificInfo` (`iotVersion`,
  `ecallSupported`, `fallbackSupported`, `fallbackAllowedUpdateSupported`). An
  IoT eUICC's `EUICCInfo2` is therefore decoded with the SGP.32 module; this one
  follows SGP.22 and skips those members.

The full SGP.22 v3.1 module, with its renames and the v3-only types, is a
separate change (`osmocom-pysim-rsp-v3-module/`).

Commit subject on the fork:
`esim/asn1/rsp: decode the SGP.22 v3 members of EUICCInfo1 and EUICCInfo2`

On hampushellsberg-dev/pysim as `d5b3266` (2026-10-29), on top of `f2db3ab`.

## Validation

`validation.txt`: the repro before and after; every `tests/unittests` file run
the way pySim's CI runs them, unpatched and patched (identical results apart
from the new `test_esim_rsp.py`, `test_log` and `test_smpp_ota_tool` failing on
both for environment reasons); compileall.

## The YggdraSIM-side half

YggdraSIM pins hampushellsberg-dev/pysim, so the fix reaches YggdraSIM as a fork
commit plus a pin move, not as a compensation. Until the pin moves,
`Tools/Asn1TlvDecode/gsma_schema.py` decodes `EUICCInfo1` through this module
(SGP.32 v1.3 imports it from `RSPDefinitions`) and shows a v3 eUICC's
`EUICCInfo1` without the three members. `EUICCInfo2` is not affected there: the
SGP.32 v1.3 module declares its own, with the v3 members.

The SGP.32 module also declares its own `IoTSpecificInfo`, so after this patch
two modules of that joint compile declare the name. asn1tools then drops it from
the flat type table and the decoder resolves it per module; an SGP.32
`EUICCInfo2` with `iotSpecificInfo` content decodes to the same JSON with and
without the patch (checked against both trees, and pinned by
`test_sgp32_euicc_info2_keeps_its_iot_specific_info` in YggdraSIM).

## Stress-test checklist

- [x] Every added member decodes from a hand-built DER vector and re-encodes to the same bytes.
- [x] A v2 EUICCInfo1 decodes to the v2 member set and re-encodes byte-for-byte.
- [x] The repro fails on the pinned pySim and passes with the patch.
- [x] No other `tests/unittests` result changes.
- [ ] A real v3 eUICC's EUICCInfo1/2 decoded (lab capture).
- [ ] osmo-smdpp InitiateAuthentication with an eUICC that lists only a v3 CI key.
