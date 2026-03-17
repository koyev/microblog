"""
End-to-end tests: hit the API Gateway and verify the full flow.
Requires `docker compose up` to be running.
Run with: pytest e2e-tests/ --timeout=30
"""
import time
import pytest
import httpx

BASE_URL = "http://localhost:8080"
TIMEOUT = 10.0


@pytest.fixture(scope="session", autouse=True)
def wait_for_gateway():
    """Wait for the API gateway to be ready."""
    for _ in range(30):
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail("API Gateway did not become ready in time")


def test_gateway_health():
    resp = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    assert resp.status_code == 200


def test_users_crud():
    # Create a user
    username = f"e2e_user_{int(time.time())}"
    resp = httpx.post(f"{BASE_URL}/users", json={"username": username}, timeout=TIMEOUT)
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # List users
    resp = httpx.get(f"{BASE_URL}/users", timeout=TIMEOUT)
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert username in usernames


def test_posts_crud_and_notification():
    content = f"e2e test post {int(time.time())}"
    resp = httpx.post(f"{BASE_URL}/posts", json={"content": content}, timeout=TIMEOUT)
    assert resp.status_code == 201
    post_id = resp.json()["id"]

    # List posts
    resp = httpx.get(f"{BASE_URL}/posts", timeout=TIMEOUT)
    assert resp.status_code == 200
    contents = [p["content"] for p in resp.json()]
    assert content in contents

    # Wait for notification to be processed via RabbitMQ
    time.sleep(3)
    resp = httpx.get(f"{BASE_URL}/notifications", timeout=TIMEOUT)
    assert resp.status_code == 200
    messages = [n["message"] for n in resp.json()]
    assert any(content[:30] in m for m in messages), f"Notification not found. Got: {messages}"


def test_comments_crud():
    text = f"e2e comment {int(time.time())}"
    resp = httpx.post(f"{BASE_URL}/comments", json={"text": text}, timeout=TIMEOUT)
    assert resp.status_code == 201

    resp = httpx.get(f"{BASE_URL}/comments", timeout=TIMEOUT)
    assert resp.status_code == 200
    texts = [c["text"] for c in resp.json()]
    assert text in texts
