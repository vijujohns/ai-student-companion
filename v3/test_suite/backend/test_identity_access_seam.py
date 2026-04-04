"""Identity + Access extraction seam tests.

Verifies that auth/profile routes delegate through `services.identity`
rather than importing and calling auth/user manager helpers directly.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="module")
def client():
    heavy = [
        "sentence_transformers", "faiss", "numpy", "numpy.core",
        "tqdm", "tqdm.auto", "pypdf", "deep_translator",
        "llama_cpp", "openai", "docx", "python_docx",
    ]
    injected = {}
    for pkg in heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            injected[pkg] = True

    sys.modules["sentence_transformers"].SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module
        from fastapi.testclient import TestClient

        with (
            patch.object(main_module, "load_index", return_value=None),
            patch.object(main_module, "load_knowledge_base", return_value=None),
            patch.object(main_module, "init_db", return_value=None),
            patch("threading.Thread"),
        ):
            from app.modules.db import init_db

            init_db()
            with TestClient(main_module.app, raise_server_exceptions=True) as c:
                yield c
    finally:
        for pkg in injected:
            del sys.modules[pkg]


@pytest.fixture(autouse=True)
def clear_client_cookies(client):
    client.cookies.clear()


def login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestIdentityAccessRouteSeam:
    def test_login_route_uses_identity_service_registry(self, client):
        expected = {
            "access_token": "stub-token",
            "token_type": "bearer",
            "role": "student",
            "username": "student",
            "email": "student@example.com",
        }
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.login.return_value = expected
            resp = client.post("/login", json={"email": "student@example.com", "password": "student123"})

        assert resp.status_code == 200
        assert resp.json()["access_token"] == "stub-token"
        args = mock_services.identity.login.call_args.args
        assert args[0] == "student@example.com"
        assert args[1] == "student123"
        assert args[2] is not None

    def test_auth_session_route_uses_identity_service_registry(self, client):
        token = login(client)
        expected = {
            "authenticated": True,
            "username": "student",
            "email": "student@example.com",
            "role": "student",
        }
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.get_auth_session.return_value = expected
            resp = client.get("/auth/session", headers=auth_headers(token))

        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True
        assert mock_services.identity.get_auth_session.call_count == 1
        user_arg = mock_services.identity.get_auth_session.call_args.args[0]
        assert user_arg["username"] == "student"

    def test_logout_route_uses_identity_service_registry(self, client):
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.logout.return_value = {"status": "logged_out"}
            resp = client.post("/logout")

        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"
        assert mock_services.identity.logout.call_count == 1

    def test_register_route_uses_identity_service_registry(self, client):
        expected = {
            "status": "registered",
            "email": "seam-user@example.com",
            "role": "student",
        }
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.register.return_value = expected
            resp = client.post(
                "/register",
                json={
                    "first_name": "Seam",
                    "last_name": "User",
                    "email": "seam-user@example.com",
                    "dob": "2005-05-05",
                    "password": "pass1234",
                    "role": "student",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["email"] == "seam-user@example.com"
        mock_services.identity.register.assert_called_once_with(
            first_name="Seam",
            last_name="User",
            email="seam-user@example.com",
            dob="2005-05-05",
            password="pass1234",
            role="student",
        )

    def test_profile_route_uses_identity_service_registry(self, client):
        token = login(client)
        expected_profile = {
            "username": "student",
            "email": "student@example.com",
            "first_name": "Student",
            "last_name": "User",
            "dob": "2000-01-01",
        }
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.update_profile.return_value = expected_profile
            resp = client.put(
                "/profile",
                headers=auth_headers(token),
                json={
                    "first_name": "Student",
                    "last_name": "User",
                    "dob": "2000-01-01",
                    "email": "student@example.com",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
        mock_services.identity.update_profile.assert_called_once_with(
            username="student",
            first_name="Student",
            last_name="User",
            dob="2000-01-01",
            email="student@example.com",
        )

    def test_reset_password_route_uses_identity_service_registry(self, client):
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.reset_password.return_value = True
            resp = client.post(
                "/reset-password",
                json={
                    "email": "student@example.com",
                    "dob": "2000-01-01",
                    "new_password": "newPass123",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "password_reset"
        mock_services.identity.reset_password.assert_called_once_with(
            email="student@example.com",
            dob="2000-01-01",
            new_password="newPass123",
        )

    def test_reset_password_route_returns_400_when_service_denies(self, client):
        with patch("app.api.routes.services") as mock_services:
            mock_services.identity.reset_password.return_value = False
            resp = client.post(
                "/reset-password",
                json={
                    "email": "student@example.com",
                    "dob": "1900-01-01",
                    "new_password": "newPass123",
                },
            )

        assert resp.status_code == 400
