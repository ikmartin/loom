"""Overleaf's git, stood in for the write suite: put on PYTHONPATH by `tests/served.ts` for a test that asks for it, with LOOM_OVERLEAF_STAND_IN naming a folder of the test's own.

Python imports this as it starts, before loom runs. It points the mirror where the Python suite's isolation points it (`loom/tests/conftest.py`): projects are bare repositories in the folder's `projects/`, one an id, and the credential helper is a file there in place of the macOS Keychain, so no test reaches Overleaf or the Keychain. Without the variable it does nothing.
"""

import os

_STAND_IN = os.environ.get("LOOM_OVERLEAF_STAND_IN")
if _STAND_IN:
    import loom.overleaf as _overleaf

    _overleaf.BASE = os.path.join(_STAND_IN, "projects")
    _overleaf.HELPER = f"store --file={os.path.join(_STAND_IN, 'keychain-stand-in')}"
    _overleaf.PROTOCOLS = ("https", "http", "file")
