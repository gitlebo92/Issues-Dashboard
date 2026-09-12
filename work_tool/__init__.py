"""
work_tool - NOC / field ops domain logic.

This used to be one 10,000-line module. It is now a package, but the public
surface is deliberately identical: every name that was reachable as
`work_tool.<name>` still is, so nothing that imports it needed to change.

Add new code to the focused module it belongs to, not to `_core`.
"""

from . import _core
from . import locks, weather, diagnostics, security_update

_SUBMODULES = (_core, locks, weather, diagnostics, security_update)

# Re-export every public and private name. `import *` is not enough: callers
# (and the tests) reach for underscore-prefixed helpers like _net_row_for_unit,
# and those would be dropped.
for _mod in _SUBMODULES:
    for _name, _value in vars(_mod).items():
        if not _name.startswith("__"):
            globals()[_name] = _value
del _mod, _name, _value
