import sys
import os
from pathlib import Path

# Přidá parent adresář do sys.path, aby pytest mohl najít modul 'app'
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
