import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app import create_app


@pytest.fixture
def app():
    app = create_app("testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Test client already logged in as admin."""
    c = app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin123"})
    return c
