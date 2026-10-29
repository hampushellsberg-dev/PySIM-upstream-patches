# pySim: every secure-channel log line prints twice

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`)
Base commit: `9aa8934da2415b161eb9726adad2ba7b4f35d1a7`
Affected: `pySim/log.py` (`PySimLogger.get`, `_PySimLogHandler`), seen through
`pySim/global_platform/__init__.py` and `pySim/global_platform/scp.py`

## What happens

Commit `2053877` ("pySim/scp: migrate to pySimLogger") gives both modules a
logger from `PySimLogger.get(__name__)`:

```python
# pySim/global_platform/__init__.py
log = PySimLogger.get(__name__)        # 'pySim.global_platform'
# pySim/global_platform/scp.py
log = PySimLogger.get(__name__)        # 'pySim.global_platform.scp'
```

`PySimLogger.get` adds a new `_PySimLogHandler` to whatever logger it returns:

```python
    @staticmethod
    def get(log_facility: str):
        logger = logging.getLogger(log_facility)
        handler = _PySimLogHandler(log_callback=PySimLogger._log_callback)
        logger.addHandler(handler)
        return logger
```

Python logging hands a record to the handlers of its own logger and then to
those of every ancestor while `propagate` is true. A record of
`pySim.global_platform.scp` therefore reaches two `_PySimLogHandler`
instances, and `_log_callback` prints it twice (with no print callback set,
it calls `print(record.message)`). `pySim.log` sets the root logger to DEBUG
on import, so a library user that never calls `PySimLogger.setup` sees every
DEBUG line of the SCP02 / SCP03 code twice on stdout: the KDF input
(`scp03_kdf(constant=..., context=..., base_key=..., l=...)`), the session
keys, the MAC and wrap steps. The docstring of `PySimLogger.get` speaks of
facilities such as "MAIN" or "RUNTIME". The earlier users (`runtime`,
`transport`, `card_key_provider`) pass `__name__` too, but none of their
loggers is an ancestor of another; `pySim.global_platform` and
`pySim.global_platform.scp` are the first pair that nest.

Printing DEBUG by default is how `PySimLogger` is documented to behave ("a
safe default that works for applications that ignore the presence of the
PySimLogger class"); only the duplicate is a defect.

## Repro

`repro_log_duplicate_handlers.py` calls `scp03_key_derivation` once and counts
what reaches stdout; `validation.txt` has the runs: 0 lines at `c50f4b4` (no
handler yet), 2 on master `9aa8934` and on hampushellsberg-dev/pysim
`f2db3ab`, 1 with the patch.

## Fix

`pysim-log-duplicate-handlers.patch`: `_PySimLogHandler.emit` marks the record
and returns early for a record already marked, so a record prints at the first
handler it meets on its way up and not again. It does not depend on import
order or on which loggers carry a handler, and records still propagate to
handlers an application installs on the root logger.

On hampushellsberg-dev/pysim as `74f5002` (2026-10-29, `log: print a record only
once when loggers are nested`), with `test_06_nested_loggers` in
`tests/unittests/test_log.py`: without the fix that test sees its record three
times, with it once.

## YggdraSIM-side compensation

`yggdrasim_common/pysim_log_gate.py::install_pysim_secure_channel_log_gate`
puts a filter on the `_PySimLogHandler`s of `pySim.global_platform` and
`pySim.global_platform.scp`: a record already printed by a nearer handler is
dropped, and a record below INFO is dropped while `YGGDRASIM_GLOBAL_DEBUG` is
off (that part is YggdraSIM's choice, not a pySim defect). It probes its own
effect and raises `PySimLogGateMismatch` when a probe record still prints more
than once. `SCP03/crypto/session.py` (`_resolve_kdf`) and
`SCP03/crypto/scp02_session.py` install it; `tests/test_pysim_log_gate.py`
pins the line counts. Once pySim prints a record once, the deduplication is a
no-op and the debug gate stays.

## Stress-test checklist

- [x] SCP03 KDF on master: 2 lines before, 1 with the patch.
- [x] pySim `tests/unittests/test_log.py`: same result with and without the patch.
- [x] The patch applies to master `9aa8934` and to `f2db3ab`.
- [ ] A record logged on `pySim.global_platform` itself (one handler on its way up): still one line.
- [ ] An application that installs a root handler still receives every record once.
- [ ] `PySimLogger.setup(print_callback=...)`: the callback is called once per record.
- [ ] Upstream merge request.
