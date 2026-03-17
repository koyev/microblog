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


def test_list_comments_empty(client):
    c, mock_session = client
    mock_session.query.return_value.all.return_value = []
    resp = c.get("/comments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_comment(client):
    c, mock_session = client
    mock_comment = MagicMock()
    mock_comment.id = 1
    mock_comment.text = "Great post!"
    mock_session.refresh.side_effect = lambda obj: None

    with patch("main.Comment") as MockComment:
        MockComment.return_value = mock_comment
        resp = c.post("/comments", json={"text": "Great post!"})

    assert resp.status_code == 201
    assert resp.json()["text"] == "Great post!"
