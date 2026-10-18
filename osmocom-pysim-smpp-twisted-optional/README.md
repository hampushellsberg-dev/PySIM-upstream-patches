# pySim: smpp.twisted3 is a hard requirement that only one script needs

Target: https://gitea.osmocom.org/sim-card/pysim.git (`master`), mirrored at
https://github.com/osmocom/pysim; observed at commit
`c50f4b4a0222a964710ce3124a66fe13c804be65`.
Affected: `setup.py` (`install_requires`), `requirements.txt`.

## The problem

`setup.py` lists `smpp.twisted3 @ git+https://github.com/jookies/smpp.twisted`
in `install_requires`, and `requirements.txt` carries the same line. The
only code that imports it is `pySim-smpp2sim.py`, the SMPP-to-SIM bridge
script; `contrib/smpp-ota-tool.py` and the `smdpp` extra use `smpplib`,
which is a different library. None of the `pySim/` package modules import
`smpp.twisted`, so every consumer of the library, every `pySim-shell.py`
user included, installs a Twisted stack it never loads.

That stack is not free. Every release of `smpp.twisted3` (0.4 through 0.8)
declares `Twisted~=23.10.0`, so the resolver is held at Twisted 23.10.0,
which carries three open advisories:

| Advisory | CVE | Severity | Fixed in |
|---|---|---|---|
| GHSA-grgv-6hw6-v9g4 | CVE-2026-42304 | high | Twisted 26.4.0 |
| GHSA-cf56-g6w6-pqq2 | CVE-2024-41810 | medium | Twisted 24.7.0 |
| GHSA-c8m8-j448-xjx7 | CVE-2024-41671 | medium | Twisted 24.7.0 |

A downstream project that depends on pySim cannot move Twisted at all: the
`~=23.10.0` specifier sits in a dependency it does not control, and no
release of `smpp.twisted3` relaxes it. The vulnerable code is never
executed by such a project, but it is installed, shipped in frozen
bundles, and flagged by every dependency scanner that reads the lock.

## Proposed change

Move the requirement to an extra so the bridge script is opt-in and the
library stays lean:

```text
pip install pysim            # library and shells, no Twisted
pip install "pysim[smpp2sim]" # adds smpp.twisted3 for pySim-smpp2sim.py
```

`pysim-smpp-twisted-optional.patch` makes exactly that change to `setup.py`
and `requirements.txt`. `pySim-smpp2sim.py` is untouched: without the extra
it fails at its first `import smpp.twisted...` with a plain `ImportError`
naming the missing module, which is the same signal the `smdpp` extra
already relies on for `klein`.

## Reproduction

```bash
python -m venv /tmp/pysim-venv && /tmp/pysim-venv/bin/pip install \
    "pysim @ git+https://github.com/osmocom/pysim@c50f4b4a0222a964710ce3124a66fe13c804be65"
/tmp/pysim-venv/bin/python -c "import twisted; print(twisted.__version__)"
# 23.10.0 -- installed by a project that never imports it
/tmp/pysim-venv/bin/python - <<'EOF'
import pkgutil, importlib, pySim
hits = [m.name for m in pkgutil.walk_packages(pySim.__path__, "pySim.")
        if "smpp.twisted" in open(importlib.util.find_spec(m.name).origin).read()]
print("pySim modules importing smpp.twisted:", hits)   # []
EOF
```

## What YggdraSIM does meanwhile

`pyproject.toml` (`[tool.uv]`) overrides the requirement with a marker that
can never hold (`smpp-twisted3 ; python_version < '0'`), so the resolver
drops it and Twisted, `smpp.pdu3` and Twisted's own dependency tail leave
`uv.lock`, the synced environments and the bundles. The `smpp.pdu` codec
that `SCP11/local_access/session.py` uses is pySim's separate `smpp.pdu`
requirement and stays. `tests/test_dependency_overrides.py` pins the
effect and fails the day the pinned pySim no longer declares
`smpp-twisted3`, so the override cannot outlive its cause. A `pip install`
from the sdist ignores the override and keeps pySim's declaration; that
path is only fixed by this patch landing upstream, or by pinning a pySim
fork that carries it.

## Stress-test checklist

- [x] `uv lock` after the override: 139 packages become 130; the nine that
      leave are `smpp-twisted3`, `smpp-pdu3`, `twisted`,
      `twisted-iocpsupport`, `automat`, `constantly`, `hyperlink`,
      `incremental`, `zope-interface`; nothing is added.
- [x] `uv sync --frozen --extra full --extra test --extra mcp` from the new
      lock: `import twisted` and `import smpp.twisted` raise `ImportError`;
      `from smpp.pdu import operations, pdu_types` succeeds and exposes
      `DataCoding` and `SubmitSM`; `pySim.transport`, `pySim.esim.saip` and
      `pySim.global_platform` import.
- [x] `tests/test_scp11_local_access.py` (the SMPP PDU path of local-access
      sessions), `tests/test_repo_module_import_smoke.py` (every module in
      the tree) and `tests/test_scp03_pysim_parity.py` pass in that
      environment.
- [x] `uv lock --check --python 3.11`, the CI lock gate, is clean.
- [ ] Upstream: `pip install "pysim[smpp2sim]"` from the patched tree still
      resolves `smpp.twisted3`, and `pySim-smpp2sim.py --help` runs; a plain
      `pip install pysim` no longer installs Twisted.
