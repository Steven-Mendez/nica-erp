"""Test-only helpers shared across suites.

Never import this package from productive code — the import-linter
contract ``testing-helpers-not-in-prod`` enforces it.
"""

from shared_kernel.testing.query_count import assert_query_count

__all__ = ["assert_query_count"]
