"""Shared test factories.

Builders for canonical-shape domain objects + DB row seeders. Imported as
``from tests._factories.identity import make_password`` etc. Lives under
``tests/`` so it stays out of every production import path while remaining
visible to mypy and pytest. The leading underscore signals "test
infrastructure, not production code".
"""
