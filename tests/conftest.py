"""Test setup: point the app at a throwaway SQLite file BEFORE importing it."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="retaildesk-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def owner_token(client):
    """Register one demo store owner and return a valid JWT for it."""
    res = client.post(
        "/api/auth/register",
        json={
            "store_name": "Test Store",
            "name": "Test Owner",
            "email": "owner@test.in",
            "password": "owner1234",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="session")
def staff_token(client, owner_token):
    res = client.post(
        "/api/auth/staff",
        json={"name": "Test Staff", "email": "staff@test.in", "password": "staff1234"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res.status_code == 201, res.text
    login = client.post(
        "/api/auth/login", data={"username": "staff@test.in", "password": "staff1234"}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}
