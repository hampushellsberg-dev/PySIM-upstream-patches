# pySim: a security domain key loses keyAccess and keyCounterValue on re-encode

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Checked on: master `0178f44`, hampushellsberg-dev/pysim `f2db3ab`
Affected: `pySim/esim/saip/__init__.py`, `SecurityDomainKey`, `ProfileElementSD`

## What happens

TCA SAIP V3.4.1 section 8.6.3 (page 56) defines the keys of a PE-SecurityDomain as

```asn1
KeyObject ::= SEQUENCE {
  keyUsageQualifier [21] OCTET STRING (SIZE (1..2)),
  keyAccess [22] OCTET STRING (SIZE (1)) DEFAULT '00'H,
  keyIdentifier [2] OCTET STRING (SIZE (1)),
  keyVersionNumber [3] OCTET STRING (SIZE (1)),
  keyCounterValue [5] OCTET STRING OPTIONAL,
  keyComponents SEQUENCE (SIZE (1..MAX)) OF SEQUENCE { ... }
}
```

and says of the counter: "If the keyCounterValue is present, it indicates the
initial counter associated for that keyset. If it is absent, the initial counter
value shall be set by the eUICC according to the default value of the related
protocol".

`SecurityDomainKey.from_saip_dict()` reads the usage qualifier, the KID, the KVN
and the components, and `to_saip_dict()` writes the same four:

```python
    def to_saip_dict(self) -> dict:
        return {'keyUsageQualifier': KeyUsageQualifier.build(self.key_usage_qualifier),
                'keyIdentifier': bytes([self.key_identifier]),
                'keyVersionNumber': bytes([self.key_version_number]),
                'keyComponents': [k.to_saip_dict() for k in self.key_components]}
```

`ProfileElementSD._pre_encode()` rebuilds `keyList` from those objects
(`self.decoded['keyList'] = [x.to_saip_dict() for x in self.keys]`), so decoding
and re-encoding a PE-SecurityDomain drops a non-default `keyAccess` and any
`keyCounterValue` without an error. The card then creates the keyset with the
default key access and the protocol's default counter.

## Repro

`repro_sd_key_access_counter.py` takes the PE-SecurityDomain of the TS.48
profile that ships with pySim, sets keyAccess '01' and keyCounterValue '000001'
on its first key, encodes it with pySim's compiled module, then decodes and
re-encodes it through `ProfileElement`:

```
master 0178f44:  out: keyAccess 00, keyCounterValue absent, 361 bytes -> FAIL (exit 1)
with the patch:  out: keyAccess 01, keyCounterValue 000001, 369 bytes -> PASS (exit 0)
```

## Fix

`pysim-saip-sd-key-access-counter.patch`, on hampushellsberg-dev/pysim as
`1460a87` (`esim.saip: keep keyAccess and keyCounterValue of security domain
keys`): `SecurityDomainKey` takes `key_access` (default 0) and
`key_counter_value` (default None), reads both in `from_saip_dict()` and writes
them in `to_saip_dict()`; `keyAccess` only when it differs from its DEFAULT. The
DER encoder drops a member equal to its DEFAULT anyway (probed: `keyAccess '00'`
encodes the same as no keyAccess), so existing encodings are unchanged.
`SaipTest.test_sd_key_access_and_counter` in `tests/unittests/test_esim_saip.py`
pins the round trip; it fails without the fix.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_lossless_security_domain_encoding`
wraps `ProfileElementSD._pre_encode` and puts back only the fields the rebuilt
`keyList` entries omit, matched by KVN and KID. With this fix nothing is omitted,
so the wrapper restores nothing; it goes in the change that moves the pin.

## Stress-test checklist

- [x] A non-default keyAccess and a keyCounterValue survive decode and re-encode.
- [x] A key with the default keyAccess and no counter encodes as before (the TS.48
      profile re-encodes byte for byte, `test_reencode_sequence`).
- [x] `SecurityDomainKey(...)` callers without the new arguments are unchanged
      (personalization passes keywords; `test_configurable_parameters` passes).
- [x] No other `tests/unittests` result changes.

## Validation

`validation.txt`: the repro on master and on the fork commit; every
`tests/unittests` file, before and after.
