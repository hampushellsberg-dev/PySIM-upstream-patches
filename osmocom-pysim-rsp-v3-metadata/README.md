# pySim RSP schema: StoreMetadataRequest stops at SGP.22 v2

`pySim/esim/asn1/rsp/rsp.asn` defines `StoreMetadataRequest` with the nine
members SGP.22 v2 specifies. SGP.22 v3.1 §5.5.3 adds ten more, and the module
carries none of the types they reference.

## What goes wrong

`asn1tools` does not reject a payload key the compiled schema does not define —
it **silently ignores it**. Encoding a `StoreMetadataRequest` with
`hriServerAddress` set returns the same bytes as encoding without it, raises
nothing, and reports nothing. A caller has no way to tell the field was lost:

```
baseline StoreMetadataRequest: 22 bytes

  DROPPED rpmConfiguration                     (expected tag BA) -- identical to baseline
  DROPPED hriServerAddress                     (expected tag 9B) -- identical to baseline
  ...
FAIL: 10 of 10 members unreachable
```

This matters beyond metadata authoring: an eUICC advertises
`hriServerAddressSupport`, `serviceDescriptionSupport`,
`estimatedProfileSizeIndicationSupport` and `deviceChangeSupport` in
`EUICCInfo2.euiccRspCapability`, so a profile can be provisioned against a card
that claims support for fields no encoder built on this schema can write.

## Repro

```
python repro_rsp_v3_storemetadata.py
```

Exits non-zero against an unpatched pySim, listing each member that encoded to
the baseline bytes. Exits zero once the patch is applied.

## The patch

`pysim-rsp-v3-storemetadata.patch` adds the ten members to
`StoreMetadataRequest` and the types they reference, transcribed from SGP.22
v3.1 Annex H:

| Member | Tag | Type added |
|---|---|---|
| `serviceSpecificDataStoredInEuicc [34]` | `BF22` | `VendorSpecificExtension` |
| `serviceSpecificDataNotStoredInEuicc [35]` | `BF23` | — |
| `rpmConfiguration [26]` | `BA` | `RpmConfiguration`, `RpmType` |
| `hriServerAddress [27]` | `9B` | — |
| `serviceProviderMessage [30]` | `BE` | `LocalisedTextMessage` |
| `lprConfiguration [28]` | `BC` | `LprConfiguration` |
| `enterpriseConfiguration [29]` | `BD` | `EnterpriseConfiguration` |
| `serviceDescription [31]` | `9F1F` | `ServiceDescription` |
| `deviceChangeConfiguration [32]` | `BF20` | `DeviceChangeConfiguration` |
| `estimatedProfileSize [33]` | `9F21` | — |

Members are declared in the order SGP.22 v3.1 §5.5.3 lists them, so the encoder
emits them in that order.

### One deviation from the published module

`VendorSpecificExtension` is published as an information object class:

```asn1
vendorOid [0] OPENTYPE.&typeId,
vendorSpecificData [1] OPENTYPE.&Type
```

`asn1tools` has no `OPENTYPE` class to resolve, so the patch types the two
fields as `OBJECT IDENTIFIER` and `ANY`. On the wire this is the same
encoding — an OID followed by the vendor's own DER — but nothing validates
that the DER matches the OID's registered type. Callers pass
`vendorSpecificData` as raw bytes.

## Validation

`validation.txt` holds the before/after repro output plus:

- a round-trip of all twelve members (encode, decode, compare) — identical;
- proof that the SGP.22 v2 encoding is byte-for-byte unchanged, so the patch is
  purely additive and no existing caller shifts.

`LocalisedTextMessage.languageTag` is `DEFAULT "en"`, so omitting it encodes
nothing and decodes back as `"en"`. That is the ASN.1 behaviour, not a loss.

## Re-applying

`pysim/` is untracked in this repo, so a pySim update silently reverts this and
the ten members go back to being dropped without an error. Re-apply with:

```
cd pysim && patch -p1 < ../upstream_patches/osmocom-pysim-rsp-v3-metadata/pysim-rsp-v3-storemetadata.patch
```

`tests/test_metadata_codec_v3_members.py` fails closed when the schema lacks
the members, so the suite catches a reverted tree rather than shipping profiles
with the fields quietly missing.

## The YggdraSIM-side half

Patching an on-disk checkout only fixes the machine it runs on. `pysim/` is
gitignored, `pyproject.toml` pins upstream `osmocom/pysim`, and an operator who
`pip install`s the project gets the nine-member schema -- so this patch alone
leaves the released tool unable to author v3 metadata.

`SCP11/rsp_v3_schema.py` closes that gap without a forked dependency.
`pySim.esim.compile_asn1_subdir` concatenates the ASN.1 files in a directory and
compiles the string, so YggdraSIM reads the same text, declares the ten members
and the eight types they reference, and compiles that instead. The result is
identical to the patched tree: 59 bytes where the stock schema writes 53, and
`estimatedProfileSize` decodes back.

It is scoped and self-retiring. The anchor line
(`profilePolicyRules [25] PprIds OPTIONAL`) occurs in three types, so the
substitution is confined to the `StoreMetadataRequest` block -- a first-match
replace patches the wrong type and yields a nine-member schema with no error.
Once this patch lands upstream the anchor stops matching, the supplement becomes
a no-op, and `test_supplement_is_skipped_once_upstream_declares_them` pins that.
`rsp_type_members` reads the compiled member set back at the point of use, so a
supplement that stops applying is reported rather than silently losing fields.

Delete `SCP11/rsp_v3_schema.py` and its call site in `SCP11/pysim_support.py`
when the pinned pySim carries the members itself.

## Stress-test checklist

- [x] Every v3 member encodes under the tag SGP.22 v3.1 §5.5.3 assigns it.
- [x] Every v3 member round-trips encode → decode unchanged.
- [x] The v2 member set encodes byte-for-byte as it did before the patch.
- [x] An absent `v3` block in the metadata document changes no output byte.
- [x] `DeviceChangeConfiguration` encodes under both CHOICE alternatives.
- [x] `RpmConfiguration.managingDpList` accepts several entries.
- [ ] Exercised against a physical eUICC that advertises the v3 capability bits.
