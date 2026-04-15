"""Shared test fixtures."""
import os

import pytest


@pytest.fixture(autouse=True)
def _set_test_env():
    """Set environment variables for testing."""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DEV_AUTH_BYPASS"] = "true"
    yield
