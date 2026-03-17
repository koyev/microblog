import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture
def client():
    with patch("main.engine"), \
         patch("main.Base.metadata.create_all"), \
         patch("main.SessionLocal") as mock_session_cls, \
         patch("main.get_rabbitmq_channel", new_callable=AsyncMock) as mock_mq:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_mq.return_value = AsyncMock()

        from main import app
        with TestClient(app) as c:
            yield c, mock_session


def test_health(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_posts_empty(client):
    c, mock_session = client
    mock_session.query.return_value.all.return_value = []
    resp = c.get("/posts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_post(client):
    c, mock_session = client
    mock_post = MagicMock()
    mock_post.id = 1
    mock_post.content = "Hello world"
    mock_session.refresh.side_effect = lambda p: None

    with patch("main.Post") as MockPost:
        MockPost.return_value = mock_post
        resp = c.post("/posts", json={"content": "Hello world"})

    assert resp.status_code == 201
    assert resp.json()["content"] == "Hello world"
