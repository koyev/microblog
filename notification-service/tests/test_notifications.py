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


def test_list_notifications_empty(client):
    c, mock_session = client
    mock_session.query.return_value.all.return_value = []
    resp = c.get("/notifications")
    assert resp.status_code == 200
    assert resp.json() == []


def test_process_message_stream():
    from main import process_message_stream
    messages = ["test message 1", "test message 2"]
    # Should complete without errors
    process_message_stream(messages)


def test_save_notification():
    with patch("main.SessionLocal") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        from main import save_notification
        save_notification("test notification")
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
