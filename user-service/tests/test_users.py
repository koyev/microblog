import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    with patch("main.engine"), \
         patch("main.Base.metadata.create_all"), \
         patch("main.SessionLocal") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        from main import app
        with TestClient(app) as c:
            yield c, mock_session


def test_health(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_users_empty(client):
    c, mock_session = client
    mock_session.query.return_value.all.return_value = []
    resp = c.get("/users")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_user(client):
    c, mock_session = client
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.username = "alice"
    mock_session.add.return_value = None
    mock_session.commit.return_value = None
    mock_session.refresh.side_effect = lambda u: setattr(u, "id", 1)

    with patch("main.User") as MockUser:
        MockUser.return_value = mock_user
        resp = c.post("/users", json={"username": "alice"})

    assert resp.status_code == 201
    assert resp.json()["username"] == "alice"


def test_create_user_duplicate(client):
    c, mock_session = client
    existing = MagicMock()
    existing.username = "alice"
    mock_session.query.return_value.filter.return_value.first.return_value = existing
    resp = c.post("/users", json={"username": "alice"})
    assert resp.status_code == 409
