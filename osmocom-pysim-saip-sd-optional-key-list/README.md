# pySim: `ProfileElementSD` requires `keyList` and encodes an empty one

## What happens

`pySim/esim/saip/__init__.py`, `ProfileElementSD`:

```python
    def _post_decode(self):
        self.usip = self.C9()
        self.usip.from_bytes(self.decoded['instance']['applicationSpecificParametersC9'])
        self.keys = [SecurityDomainKey.from_saip_dict(x) for x in self.decoded['keyList']]

    def _pre_encode(self):
        self.decoded['keyList'] = [x.to_saip_dict() for x in self.keys]
        self.decoded['instance']['applicationSpecificParametersC9'] = self.usip.to_bytes()
```

1. `_post_decode` reads `decoded['keyList']` unconditionally, so decoding a
   PE-SecurityDomain that omits the member raises `KeyError: 'keyList'`. A
   supplementary SD without keys of its own is such an element, and so is any
   SD whose last key an editor removes.
2. `_pre_encode` writes `keyList` from `self.keys` every time, so an SD without
   keys -- the state `ProfileElementSD()` starts in, before `add_key()` -- is
   encoded with an empty `keyList` SEQUENCE OF.

## Why it is wrong

TCA eUICC Profile Package Interoperable Format Technical Specification
V3.4.1, section 8.6.1 (page 55):

```
PE-SecurityDomain ::= SEQUENCE {
      sd-Header PEHeader,
      instance ApplicationInstance,
      keyList SEQUENCE (SIZE (1..MAX)) OF KeyObject OPTIONAL,
      ...
```

The member is optional, so an element without it is valid and has to decode;
and its size constraint is 1..MAX, so an empty list is no valid encoding --
an SD without keys omits the member. asn1tools does not check the size
constraint on encode, so the empty list reaches the package unnoticed.

## Repro

`repro_sd_optional_key_list.py` encodes an SD without keys through pySim, and
decodes with pySim an SD that omits `keyList`, encoded straight through the
compiled module:

```
## pinned pySim
SD without keys, encoded: keyList present with 0 entries -> WRONG
SD omitting keyList, decoded: KeyError 'keyList' -> WRONG
## pinned pySim + YggdraSIM compensation (--compensated)
SD without keys, encoded: keyList absent -> OK
SD omitting keyList, decoded: decoded, 0 keys, keyList still absent -> OK
## pinned pySim with 0001-saip-sd-key-list-is-optional.patch
SD without keys, encoded: keyList absent -> OK
SD omitting keyList, decoded: decoded, 0 keys, keyList still absent -> OK
## pinned pySim with the patch + YggdraSIM compensation (--compensated)
SD without keys, encoded: keyList absent -> OK
SD omitting keyList, decoded: decoded, 0 keys, keyList still absent -> OK
```

The pinned pySim is the `pySim 1.0` in the YggdraSIM venv; the gitignored
`pysim/` checkout carries the same two methods.

## Fix

`0001-saip-sd-key-list-is-optional.patch` reads the member with
`decoded.get('keyList', [])` and writes it only when there is a key, removing
it otherwise.

## YggdraSIM-side compensation

`Tools/ProfilePackage/saip_pysim_compat.py::install_optional_security_domain_key_list`
wraps both methods. The decode wrapper hands upstream an empty list for a
missing member and takes it out again, so the element keeps omitting it, and
raises `SaipSecurityDomainKeyListMismatch` when that decodes to keys; the
encode wrapper drops the list upstream wrote when it is empty. On a pySim with
the fix both wrappers change nothing (last two runs above).
`saip_json_codec.ensure_workspace_pysim_on_path` and
`SIMCARD/saip_pysim_specs.py` install it beside the other SAIP compensations.
`tests/test_saip_pysim_compat.py` pins the unpatched callables through
`__wrapped__`, so it fails the day the pin moves to a pySim with the fix.

The SAIP workbench creates a blank PE-SecurityDomain without `keyList`, adds
keys through `saip.add_security_domain_key`, and removes the member with the
last key (`saip.remove_security_domain_key`); before the compensation the
rebuild after that removal failed with the `KeyError` above.

## Stress checklist

- [x] An SD without keys encodes without `keyList` and decodes back to zero keys.
- [x] An SD that omits `keyList` decodes; the element still omits it afterwards.
- [x] An SD with keys: upstream's own path, the list encoded as before.
- [x] Removing the last key and re-encoding the package (workbench round trip).
- [x] The lossless key-field wrapper (`install_lossless_security_domain_encoding`) composes with it: `keyAccess` and `keyCounterValue` still survive an encode.
- [x] PE-SSD (`ProfileElementSSD`) inherits both methods and encodes without `keyList` the same way.
- [ ] Upstream merge request.
