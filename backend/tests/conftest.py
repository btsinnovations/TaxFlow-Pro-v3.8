import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, get_db
from backend.api import app
from backend.models import User
from backend.routers.auth import get_password_hash

TEST_DB = "sqlite:///./test_taxflow.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def auth_client(client):
    # Register a test user
    resp = client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    })
    assert resp.status_code == 200, resp.text
    # Login
    resp = client.post("/api/auth/login", data={
        "username": "testuser",
        "password": "password123"
    })
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
