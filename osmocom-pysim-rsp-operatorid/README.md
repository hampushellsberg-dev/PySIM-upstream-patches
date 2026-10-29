# pySim RSP schema: OperatorId is spelled OperatorID

`pySim/esim/asn1/rsp/rsp.asn` declares the profile owner type as
`OperatorID`. SGP.22 v3.1 Annex H (page 438 of the v3.1 text) spells it
`OperatorId`, and the SGP.32 v1.3 ASN.1 module imports it under that name from
the SGP.22 module:

```
IMPORTS ... OperatorId, ... FROM RSPDefinitions {... asn1modules(1) sgp22v2(2)};
```

## What goes wrong

Compiling the published SGP.32 v1.3 module together with pySim's RSP module --
the only way to decode SGP.32 types that reference SGP.22 ones -- fails:

```
FAIL SGP.32 v1.3 module: CompileError: Type 'OperatorId' imported by module
'SGP32Definitions' not found in module 'RSPDefinitions'.
```

Every tool that wants SGP.32 decoding on top of pySim has to patch the name in
first. YggdraSIM does (`_supplement_operator_id` in
`Tools/Asn1TlvDecode/gsma_schema.py`), and placing that declaration was itself
the cause of a defect: inserted before the last `END` of pySim's `asn1/rsp`
files, it landed in a PKIX module whenever the file system listed `rsp.asn`
first.

## Repro

```
python repro_rsp_operatorid.py [path/to/SGP.32-v1.3.asn1]
```

Compiles a minimal module that imports `OperatorId` from `RSPDefinitions`, and
with the optional path the SGP.32 v1.3 module too. Exits 1 against an unpatched
pySim, 0 with the patch.

## The patch

`pysim-rsp-operatorid.patch` (apply after `pysim-rsp-v3-euiccinfo.patch` and
`pysim-rsp-v3-module.patch`; it extends their test file) adds to the v2 module

```asn1
OperatorId ::= OperatorID
```

an alias rather than a rename: `ProfileInfo`, `StoreMetadataRequest` and
`ProfilePolicyAuthorisationRule` keep referencing `OperatorID`, both names
encode the same, and nothing that encodes or decodes by either name changes.
Tests: the alias encodes like `OperatorID`; a module importing `OperatorId`
from `RSPDefinitions` compiles and encodes the owner under tag `B7`. The v3.1
module (`rsp_v3`) declares `OperatorId` itself.

Commit subject on the fork:
`esim/asn1/rsp: add OperatorId as an alias of OperatorID`

On hampushellsberg-dev/pysim as `adf97af` (2026-10-29), after `3fd51ec`.

## Validation

`validation.txt`: the repro before and after, the SGP.32 v1.3 module of the
specification library included; every `tests/unittests` file, unpatched and
with the three patches (identical apart from `test_esim_rsp.py`); the three
patches applied in order to a fresh clone reproduce the tested tree.

## The YggdraSIM-side half

`_supplement_operator_id` returns the text unchanged when it already declares
`OperatorId`, so with this patch installed it does nothing (pinned by
`test_operator_id_supplement_steps_aside_when_pysim_declares_it`). It stays
until the YggdraSIM pin carries this commit -- until then a fresh install gets
`f2db3ab`, which lacks the name -- and is deleted in the pin-move change.

## Stress-test checklist

- [x] `OperatorId` and `OperatorID` encode and decode the same.
- [x] A module importing `OperatorId` from `RSPDefinitions` compiles.
- [x] The published SGP.32 v1.3 module compiles against pySim's RSPDefinitions with no supplement.
- [x] No other `tests/unittests` result changes.
