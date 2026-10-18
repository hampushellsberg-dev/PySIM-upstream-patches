# pySim SAIP: no ProfileElement class for cdmaParameter, nonStandard, iot and opt-iot

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Base commit: `c50f4b4a0222a964710ce3124a66fe13c804be65` (the pin in `pyproject.toml`)
Affected: `pySim/esim/saip/__init__.py` (`ProfileElement.class_for_petype`,
`NaaUsim`, `ProfileElementSequence._rebuild_pes_by_naa`),
`pySim/esim/saip/templates.py` (the Section 9.10 templates)

## Gap

`ProfileElement.class_for_petype` maps every member of the `ProfileElement`
CHOICE of `PE_Definitions-3.3.1.asn` to a class except four, which the
dictionary lists as comments:

```python
            'akaParameter': ProfileElementAKA,
            # TODO: cdmaParameter
            'securityDomain': ProfileElementSD,
            ...
            # TODO: nonStandard
            ...
            # TODO: csim
            # TODO: opt-csim
```

`iot` and `opt-iot` are not mentioned at all. A package carrying one of these
elements still decodes (the ASN.1 module has the types), but the element
lands in the bare `ProfileElement`:

- no `files` dict, no `File` objects, so nothing reaches the file-system model
  (`ProfileElementSequence.mf` stays `None` when PE-IoT is the element that
  creates the MF);
- no template, so no file identifiers, SFIs, default contents or record
  layouts for the 22 + 26 files of the IoT Minimal Profile templates;
- `NaaUsim.pe_types` does not list the two types, so `pes_by_naa` is empty
  for an IoT Minimal Profile and every helper that walks the USIM NAA
  (`get_closest_prev_pe_for_templateID`, `remove_naas_of_type`, the
  personalization keys) skips it.

The IoT Minimal Profile is not exotic: TCA "Profile interoperability
technical specification" V3.4.1 Section 7.5 defines it as `ProfileHeader`,
`PE-IoT`, optionally `PE-OPT-IoT`, then the security and NAA-parameter
elements and `PE-End`, and Section 8.1 says PE-MF is not allowed in it. Every
IoT Minimal Profile therefore hits this gap on its second element.
`cdmaParameter` and `nonStandard` are two-field elements with no file
system; the missing class only costs the type-specific behaviour
(`header_name`, `mandated`) that the base class already provides.

## Fix

`pysim-saip-extra-profile-elements.patch`:

- `ProfileElementCDMA` (`cdmaParameter`) and `ProfileElementNonStandard`
  (`nonStandard`): thin `ProfileElement` subclasses, so the elements carry
  their type the way every other element does.
- `ProfileElementIoT` (`iot`): a `FsProfileElement` for TCA SAIP V3.4.1
  Section 8.3.4.8.1. The template spans two levels (the MF with EF.PL,
  EF.ICCID, EF.DIR, EF.ARR, EF.UMPC, then ADF.USIM 7FF1 with its mandatory
  files; Section 9.10.1), so the USIM rows carry `ppath=[0x7ff1]` and the
  class matches template paths both absolute and relative to the MF. `mf`
  is OPTIONAL in the element: when the element omits it, the class roots the
  template MF before placing the first file; when a preceding
  PE-GenericFileManagement created the MF (Section 8.1), that MF is reused.
- `ProfileElementOptIoT` (`opt-iot`): the optional files of Section 9.10.2
  below the ADF.USIM of the preceding PE-IoT, with DF.5GS (5FC0) and DF.SAIP
  (5FD0) as children of that ADF. The template tree of `ProfileTemplate`
  cannot express two sibling DFs inside one template (the second DF nests
  under the first), so placement follows the row's `ppath`, and a DF row the
  element leaves out is created from the template on the way down.
- `FilesIotMandatory` (OID 2.23.143.1.2.17) and `FilesIotOptional`
  (2.23.143.1.2.18), transcribed from Section 9.10.1 and 9.10.2 of V3.4.1;
  `oid.py` already defines both OIDs.
- `NaaUsim.pe_types` and `.templates` list the two types and templates;
  `_rebuild_pes_by_naa` treats `iot` as the start of the `usim` NAA, since
  PE-IoT is what creates ADF.USIM in such a profile.

The four `csim` / `opt-csim` entries stay as they are: the Section 9.7
templates are not transcribed here.

## Reproduce

`repro_saip_extra_profile_elements.py` builds the smallest IoT Minimal
Profile (header, iot, opt-iot, end) with pySim's own ASN.1 module and checks
the class lookup, the decoded classes, the file-system tree, the NAA
grouping and the DER round trip. It imports only pySim:

```bash
PYTHONPATH=/path/to/stock/pysim   python3 repro_saip_extra_profile_elements.py   # exit 1
PYTHONPATH=/path/to/patched/pysim python3 repro_saip_extra_profile_elements.py   # exit 0
```

`validation.txt` is the output of both runs against a copy of the pinned
install (`c50f4b4`) before and after the patch: 8 failures before (four
`None` lookups, no files, no MF, no NAA group), all checks passing after.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_extra_profile_elements`
installs the same classes and templates at runtime for the pinned upstream:
it wraps `class_for_petype` (deferring to upstream for every type upstream
maps), registers the templates only when the registry has none for the OID,
extends `NaaUsim.pe_types`, replaces `_rebuild_pes_by_naa` only while the
upstream source does not mention `iot`, and raises
`SaipExtraProfileElementMismatch` when the lookup or the registry does not
reflect the change afterwards. It is installed by
`saip_json_codec.ensure_workspace_pysim_on_path` (GUI, TUI, CLI) and by
`SIMCARD/saip_pysim_specs.py::_ensure_pysim_saip_compat` (card engine).
`tests/test_saip_iot_profile_elements.py::ExtraProfileElementLookupTests::test_upstream_still_lacks_the_four_types`
pins the upstream gap through the wrapper's `__wrapped__`, so the
compensation is deleted the day the pin moves past the fix.

## Stress-test checklist

- [x] Stock c50f4b4: the four lookups return `None`; the IoT elements decode
      into the bare `ProfileElement`; `pes.mf` is `None` (`validation.txt`).
- [x] Patched: `ProfileElementIoT` / `ProfileElementOptIoT` decode with their
      files; MF -> ADF.USIM 7FF1 -> EF.IMSI; DF.5GS and DF.SAIP as siblings
      below the ADF; `pes_by_naa == {'usim': [['iot', 'opt-iot']]}`.
- [x] DER round trip identical before and after (the decoded model is not
      touched; the implicit MF never reaches `decoded`).
- [x] Template rows equal the `File` members of PE-IoT and PE-OPT-IoT in the
      compiled ASN.1, no more and no fewer
      (`tests/test_saip_iot_profile_elements.py`).
- [x] PE-OPT-IoT without a preceding PE-IoT (and no ADF 7FF1 below the MF)
      raises `ValueError` instead of dereferencing `None`.
- [x] Upstream classes stay upstream's (`class_for_petype('usim') is
      ProfileElementUSIM`); installer idempotent.
- [ ] A vendor IoT Minimal Profile whose MF comes from
      PE-GenericFileManagement and whose PE-IoT omits `mf` (needs a sample
      package; the reuse path is covered by construction only).
