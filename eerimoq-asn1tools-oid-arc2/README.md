# asn1tools: OBJECT IDENTIFIER under arc 2 decodes wrongly

Upstream: https://github.com/eerimoq/asn1tools (the YggdraSIM pin, the
`hampushellsberg-dev/asn1tools-loop-fix` fork, carries the same decoder).

## What happens

`asn1tools/codecs/ber.py`:

```python
def decode_object_identifier(data, offset, end_offset):
    subidentifier, offset = decode_object_identifier_subidentifier(data,
                                                                   offset)
    decoded = [subidentifier // 40, subidentifier % 40]
```

The first subidentifier is split as `value // 40, value % 40` for every
value. That is right for arcs 0 and 1, and for arc 2 up to `2.39`; from
`2.40` on the decoder invents a first component above 2: `2.40.1` reads back
as `3.0.1`, `2.999.1` as `26.39.1`. The encoder writes `X*40 + Y` correctly,
so a decode / re-encode silently rewrites the identifier. The PER and OER
codecs import the same function.

## Why it is wrong

Rec. ITU-T X.690 (02/2021) §8.19.4 (page 14): the first subidentifier is
`(X*40) + Y`, and the NOTE says "only three values are allocated from the
root node, and at most 39 subsequent values from nodes reached by X = 0 and
X = 1". A value from 80 up therefore always means X = 2, Y = value - 80.

In a SAIP package an identifier under `2.40` and above can reach a
PE-NonStandard `issuerID` (TCA SAIP V3.4.1 §8.9), which the workbench now
edits; the template OIDs (`2.23.143...`) stay below the boundary.

## Repro

`repro_oid_arc2.py` round-trips identifiers through a compiled DER module:

```
## pinned asn1tools 0.166.0
1.3.6.1.4.1.0    06062B0601040100 -> 1.3.6.1.4.1.0    OK
2.23.143.1.2.1   060667810F010201 -> 2.23.143.1.2.1   OK
2.39.1           06027701         -> 2.39.1           OK
2.40.1           06027801         -> 3.0.1            WRONG
2.999.1          0603883701       -> 26.39.1          WRONG
2.25.1           06026901         -> 2.25.1           OK
## pinned + YggdraSIM compensation (--compensated)
(every row OK)
## pinned with ber.py.patch
(every row OK)
## pinned with ber.py.patch + YggdraSIM compensation (--compensated)
(every row OK)
```

## Fix

`ber.py.patch` decodes a first subidentifier from 80 up as `[2, value - 80]`.

## YggdraSIM-side compensation

`yggdrasim_common/asn1tools_compat.py::install_object_identifier_arc2_decoding`
wraps `decode_object_identifier`: it calls upstream and, for a first
subidentifier from 80 up, replaces the first two components with `2` and
`value - 80` -- what a fixed asn1tools returns already, so the wrapper then
changes nothing. It points the PER and OER codecs at the wrapper as well and
checks a probe decode of `2.999.1`, raising
`Asn1ObjectIdentifierDecodeMismatch` when the result is still wrong.
`Tools/ProfilePackage/saip_json_codec.py` and `SIMCARD/saip_pysim_specs.py`
install it beside the SAIP compensations, so it holds in a process once a SAIP
surface has run; the SCP11 shells compile their RSP schemas without it. `tests/test_asn1tools_compat.py`
pins the unpatched function through `inspect.unwrap`, so it fails the day the
pin moves to an asn1tools with the fix.

## Stress checklist

- [x] Arcs 0 and 1 (`0.4.0.127`, `1.3.6.1.4.1.0`): unchanged.
- [x] Arc 2 below the boundary (`2.23.143.1.2.1`, `2.25.1`, `2.39.1`): unchanged.
- [x] Arc 2 from the boundary on (`2.40.1`, `2.999.1`): decoded as encoded.
- [x] A multi-octet first subidentifier (`2.999` encodes as `88 37`).
- [x] A compiled DER module and the bare codec function agree.
- [x] PER and OER hold the same function after the install.
- [ ] Upstream merge request (eerimoq) and the pinned fork.
