"""The quilt with a Lean project that the formal tests share, as a fixture.

Defined in `test_check`; named here so the other test modules get it without importing it.
"""

from tests.unit.formal.test_check import quilt

__all__ = ["quilt"]
