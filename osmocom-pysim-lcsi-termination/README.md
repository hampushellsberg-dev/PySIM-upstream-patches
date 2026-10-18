# pySim life cycle status integer: the termination state never decodes

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Affected: `pySim/ts_102_221.py`, `LifeCycleStatusInteger._from_bytes`

## Bug 1 -- a terminated file is reported as an operational one

`LifeCycleStatusInteger._from_bytes` decides the state like this:

```python
        elif lcsi & 0x05 == 0x05:
            ret = 'operational_activated'
        elif lcsi & 0x05 == 0x04:
            ret = 'operational_deactivated'
        elif lcsi & 0xc0 == 0xc0:
            ret = 'termination'
```

Two things are wrong with the last branch, and either one alone hides the
termination state:

1. It is reached only after the two `& 0x05` tests, which match first. ETSI
   TS 102 221 V18.4.0 clause 11.1.1.4.9 table 11.7b codes the operational
   states as `b3 = 1` with `b1` selecting activated (`1`) or deactivated
   (`0`), leaving `b4` free, so `'0C'`..`'0F'` satisfy them: `'0D' & 0x05`
   is `0x05` and `'0C' & 0x05` is `0x04`.
2. It looks for the termination bits in `b8 b7` (`0xc0`). The table puts the
   termination state at `b4 b3 = 1 1`, i.e. mask `0x0c`. Bits `b8`..`b5` are
   the table's proprietary indicator; a value with `b8 b7` both set is
   proprietary, never a state.

So the entire termination state -- `'0C'`, `'0D'`, `'0E'`, `'0F'`, the four
values table 11.7b defines for it -- decodes as an operational state, and the
branch as written can never be taken by any value the table defines.

`_to_bytes` in the same class encodes `'termination'` as `b'\x0c'`, so pySim
does not round trip its own output:

```text
'termination' -> 8a010c -> 'operational_deactivated'
```

### Harm

A terminated file is a file that can never be used again: TS 102 221
clause 11.1.1.4.9 points at the TERMINATE DF / TERMINATE EF commands of
ETSI TS 102 222 V17.1.0 clauses 6.7 and 6.8, whose effect is irreversible.
Decoding one as "operational, deactivated" tells the reader the opposite of
what the card said -- that the file is intact and an ACTIVATE FILE would
bring it back. Every consumer of `FcpTemplate` inherits this: a SELECT
response, a file-system dump, a profile audit.

## Bug 2 -- proprietary values are reported as operational states

The same ladder gives a state name to values table 11.7b reserves. The last
two rows of the table read:

```text
        ≠0            X   X   X   X    Proprietary
              Any other value          RFU
```

where the `≠0` spans `b8`..`b5`. So `'15'` (`b5` and `b3` and `b1` set) is
proprietary, but `0x15 & 0x05 == 0x05` makes pySim call it
`operational_activated`. The fix tests `b8`..`b5` first and lets such a value
fall through to the numeric return the function already uses for RFU codings
(`'02'` -> `2`).

## Fix

Test the proprietary indicator first, then the termination state, then the
operational states, and mask the termination state with `0x0c`. See
`pysim-lcsi-termination.patch`, which also adds `('8a010c', 'termination')`
to the class's `_test_de_encode` vectors so the round trip is covered by
pySim's own de/encode test.

## Files

- `pysim-lcsi-termination.patch` -- the fix, against `pySim/ts_102_221.py`.
- `repro_lcsi_termination.py` -- standalone repro, no YggdraSIM imports. Walks
  every value of table 11.7b and the `'termination'` round trip.
- `validation.txt` -- before/after output of the repro, the same FCP template
  decoded both ways, and YggdraSIM's own decoder for comparison.

## Stress-test checklist

- [x] `'0C'`, `'0D'`, `'0E'`, `'0F'` all decode as `termination`.
- [x] `'04'` and `'06'` still decode as `operational_deactivated`, `'05'` and
      `'07'` as `operational_activated` -- the fix must not move the
      operational states, whose `b2` is "-" in the table.
- [x] `'00'`, `'01'`, `'03'` unchanged.
- [x] `'02'` (RFU) still returns the raw integer.
- [x] `'12'` and `'15'` (proprietary) return the raw integer instead of a
      state name.
- [x] `'termination'` encodes to `8a010c` and decodes back to `'termination'`.
- [x] `_test_de_encode` passes for both vectors, decode and encode.
- [x] A complete `FcpTemplate` carrying `8A 01 0C` decodes with
      `life_cycle_status_integer = 'termination'` and every other member
      unchanged.
- [x] `'08'` (`b4` alone) is unchanged: neither operational nor termination,
      returned as the integer `8`.

## YggdraSIM-side compensation

None is needed in the product code: `SCP03/logic/fs.py::_lcs_name` reads
table 11.7b correctly and already names `'0C'`..`'0F'` the termination state
and `'12'` proprietary, so a stock pinned pySim does not change what
YggdraSIM reports.

What the pin costs is parity. `tests/test_scp03_spec_fs_fcp.py::PysimParityTests`
compares YggdraSIM's FCP decoder against pySim's for every state pySim gets
right, and `test_pysim_termination_state_is_a_known_upstream_gap` pins the
gap itself: it asserts pySim still answers `operational_deactivated` for
`'0C'`, and fails with a message pointing at this folder the day the pin
moves to a pySim carrying the fix. Delete that test and this folder together.
