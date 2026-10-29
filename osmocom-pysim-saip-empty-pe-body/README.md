# pySim: a profile carrying an rfu PE fails to load

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Checked on: master `0178f44`, hampushellsberg-dev/pysim `f2db3ab`
Affected: `pySim/esim/saip/__init__.py`, `ProfileElement.__init__`, `ProfileElement.from_der`

## What happens

TCA SAIP V3.4.1 (page 16) reserves five alternatives of the ProfileElement
CHOICE:

```asn1
  rfu1 PE-Dummy, -- this avoids renumbering of tag values
  ...
  rfu5 PE-Dummy,
...
PE-Dummy ::= SEQUENCE {
}
```

`ProfileElement.from_der()` builds a generic `ProfileElement` for a type that
has no class of its own and sets the type only after the constructor returns:

```python
        pe_type, decoded = asn1.decode('ProfileElement', der)
        pe_cls = cls.class_for_petype(pe_type)
        if pe_cls:
            inst = pe_cls(decoded, pe_sequence=pe_sequence)
        else:
            inst = ProfileElement(decoded, pe_sequence=pe_sequence)
            inst.type = pe_type
```

The constructor treats a falsy `decoded` as "construct a new PE" and generates a
header, whose name `header_name` derives from `self.type`:

```python
        if decoded:
            self.decoded = decoded
        else:
            self.decoded = OrderedDict()
            if self.header_name:
```

A PE-Dummy decodes to `{}`, so the constructor reads a type that is not set yet
and raises `AttributeError: 'ProfileElement' object has no attribute 'type'`.
`ProfileElementSequence.parse_der()` does not catch it: a profile carrying one
rfu PE does not load at all.

## Repro

`repro_empty_pe_body.py` decodes one rfu1 PE (`ab00`) on its own, then the TS.48
profile that ships with pySim with that PE inserted before PE-End, and
re-encodes both:

```
master 0178f44:  rfu1 PE ab00: AttributeError: 'ProfileElement' object has no attribute 'type'
                 TS.48 profile + rfu1 before PE-End: AttributeError: ...   -> FAIL (exit 1)
with the patch:  rfu1 PE ab00: type rfu1, re-encodes the same
                 TS.48 profile + rfu1 before PE-End: 31 PEs, re-encodes the same -> PASS (exit 0)
```

## Fix

`pysim-saip-empty-pe-body.patch`, on hampushellsberg-dev/pysim as `3322531`
(`esim.saip: fix decoding of rfu PEs with an empty body`): the
constructor generates a header only when `decoded` is None, which is what its
docstring describes ("when constructing a PE from scratch, decoded is None").
An empty decoded body is kept as it is. No caller in pySim passes an empty dict
to mean "from scratch". `renumber_identification()` skips the rfu PE because it
has no header. `SaipTest.test_rfu_pe` in `tests/unittests/test_esim_saip.py`
pins both cases; it fails without the fix.

## YggdraSIM-side compensation

`yggdrasim_common/gui_server/actions/saip.py::_patch_pysim_profile_element`
replaces `ProfileElement.__init__` with a copy that returns early when
`header_name` raises `AttributeError`. It replaces the constructor whether or
not pySim carries the fix, so it is deleted in the change that moves the pin.

## Stress-test checklist

- [x] A lone rfu1 PE decodes and re-encodes to the same bytes.
- [x] A full profile with an rfu PE loads and re-encodes to the same bytes.
- [x] PEs constructed from scratch (decoded None) get the same header as on master
      (ProfileElementSD and ProfileElementRFM, mandated or not). That the mandated
      header lacks `identification` is a separate defect, on master as well.
- [x] No other `tests/unittests` result changes.

## Validation

`validation.txt`: the repro on master and on the fork commit; every
`tests/unittests` file, before and after.
