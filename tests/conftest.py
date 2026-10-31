"""
Pytest fixtures and configuration.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import init_db
from app.main import app
from app.provider import MockProvider


@pytest.fixture(autouse=True)
def test_db_path(monkeypatch):
    """Create a temporary SQLite database for each test to ensure complete isolation."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(settings, "ROUTER_DB", path)
    init_db(path)
    yield path
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


@pytest.fixture
def client(test_db_path):
    """FastAPI TestClient with isolated DB."""
    return TestClient(app)


@pytest.fixture
def mock_provider():
    return MockProvider()
