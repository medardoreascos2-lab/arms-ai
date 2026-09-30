"""Repository-wide pytest plugin registration.

Pytest 9 requires pytest_plugins declarations to live in the
top-level conftest rather than a nested conftest.
"""

pytest_plugins = [
    "backend.tests.test_account_switch_safety_containment_v2",
]
