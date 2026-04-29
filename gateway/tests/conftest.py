"""Shared fixtures for gateway tests."""

import os

import pytest

os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["MASK_SECRETS"] = "true"

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from gateway.src.main import app
    return TestClient(app)
