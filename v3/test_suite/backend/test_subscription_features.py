"""Tests for subscription catalog and quote foundation APIs."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import sys

    heavy = [
        "sentence_transformers",
        "faiss",
        "numpy",
        "numpy.core",
        "tqdm",
        "tqdm.auto",
        "pypdf",
        "deep_translator",
        "llama_cpp",
        "openai",
        "docx",
        "python_docx",
    ]
    injected = {}
    for pkg in heavy:
        if pkg not in sys.modules:
            sys.modules[pkg] = MagicMock()
            injected[pkg] = True

    sys.modules["sentence_transformers"].SentenceTransformer = MagicMock(return_value=MagicMock())

    try:
        import app.main as main_module

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


def login(client, email="student@example.com", password="student123"):
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestSubscriptionCatalog:
    def test_catalog_returns_class_rates_and_plans(self, client):
        token = login(client)
        resp = client.get("/subscription/catalog", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "class_rates" in body
        assert any(item["class_name"] == "Class 8" for item in body["class_rates"])
        assert "plans" in body
        assert "free" in body["plans"]
        assert isinstance(body["plans"]["free"]["entitlements"], list)

    def test_quote_applies_percent_promo(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/quote",
            json={"class_names": ["Class 8", "Class 9"], "promo_code": "WELCOME10", "auto_renew": True},
            headers=headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["subtotal_cents"] == 104800
        assert body["discount_cents"] == 10480
        assert body["total_cents"] == 94320
        assert body["auto_renew"] is True

    def test_quote_rejects_invalid_promo(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/quote",
            json={"class_names": ["Class 8"], "promo_code": "NOPE"},
            headers=headers(token),
        )
        assert resp.status_code == 400

    def test_plan_me_includes_entitlements(self, client):
        token = login(client)
        resp = client.get("/plan/me", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "plan" in body
        assert "entitlements" in body["plan"]
        assert isinstance(body["plan"]["entitlements"], list)

    def test_activate_subscription_persists_active_class(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/activate",
            json={
                "class_names": ["Class 8"],
                "promo_code": "WELCOME10",
                "auto_renew": True,
                "payment_reference": "txn-12345",
            },
            headers=headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["auto_renew"] is True
        assert body["payment_reference"] == "txn-12345"
        assert body["activation_mode"] == "manual"
        assert any(item["class_name"] == "Class 8" for item in body["active_classes"])

    def test_activate_subscription_reflects_in_plan_me_classes(self, client):
        token = login(client)
        resp = client.get("/plan/me", headers=headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "classes" in body["plan"]
        assert any(item["class_name"] == "Class 8" for item in body["plan"]["classes"])

    def test_activate_subscription_upserts_existing_class(self, client):
        token = login(client)
        first = client.post(
            "/subscription/activate",
            json={"class_names": ["Class 9"], "auto_renew": False},
            headers=headers(token),
        )
        assert first.status_code == 200

        second = client.post(
            "/subscription/activate",
            json={"class_names": ["Class 9"], "auto_renew": True},
            headers=headers(token),
        )
        assert second.status_code == 200
        body = second.json()
        class_rows = [item for item in body["active_classes"] if item["class_name"] == "Class 9"]
        assert len(class_rows) == 1
        assert class_rows[0]["auto_renew"] is True

    def test_activate_subscription_rejects_invalid_class(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/activate",
            json={"class_names": ["Class 404"], "auto_renew": True},
            headers=headers(token),
        )
        assert resp.status_code == 404

    def test_quote_rejects_empty_class_names_payload(self, client):
        token = login(client)
        resp = client.post(
            "/subscription/quote",
            json={"class_names": [], "auto_renew": False},
            headers=headers(token),
        )
        assert resp.status_code == 422

    def test_plan_me_route_uses_commercial_service_registry(self, client):
        token = login(client)
        expected = {
            "plan": {"plan_code": "free", "limits": {}, "entitlements": [], "classes": []},
            "usage": {"ask_count": 0},
        }
        with patch("app.api.subscription.services") as mock_services:
            mock_services.commercial.get_plan_me.return_value = expected
            resp = client.get("/plan/me", headers=headers(token))

        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"]["plan_code"] == "free"
        assert body["usage"]["ask_count"] == 0
        mock_services.commercial.get_plan_me.assert_called_once_with("student")

    def test_subscription_quote_route_uses_commercial_service_registry(self, client):
        token = login(client)
        expected = {
            "quote_id": "Q-12345",
            "amount": 500.0,
            "currency": "INR",
            "valid_until": "2099-01-01T00:00:00Z",
            "classes": [{"class_name": "Class 8", "annual_price_cents": 50000, "currency": "INR"}],
            "subtotal_cents": 50000,
            "discount_cents": 0,
            "total_cents": 50000,
            "promo": None,
            "billing_period": "annual",
            "auto_renew": True,
        }
        payload = {"class_names": ["Class 8"], "promo_code": None, "auto_renew": True}
        with patch("app.api.subscription.services") as mock_services:
            mock_services.commercial.quote_subscription.return_value = expected
            resp = client.post("/subscription/quote", json=payload, headers=headers(token))

        assert resp.status_code == 200
        assert resp.json()["total_cents"] == 50000
        mock_services.commercial.quote_subscription.assert_called_once_with(
            class_names=["Class 8"],
            promo_code=None,
            auto_renew=True,
        )

    def test_subscription_activate_route_uses_commercial_service_registry(self, client):
        token = login(client)
        expected = {
            "status": "active",
            "active_classes": [{"class_name": "Class 8", "auto_renew": True}],
            "payment_reference": "txn-abc",
            "activation_mode": "manual",
        }
        payload = {
            "class_names": ["Class 8"],
            "promo_code": "WELCOME10",
            "auto_renew": True,
            "payment_reference": "txn-abc",
        }
        with patch("app.api.subscription.services") as mock_services:
            mock_services.commercial.activate_subscription.return_value = expected
            resp = client.post("/subscription/activate", json=payload, headers=headers(token))

        assert resp.status_code == 200
        assert resp.json()["payment_reference"] == "txn-abc"
        mock_services.commercial.activate_subscription.assert_called_once_with(
            user_id="student",
            class_names=["Class 8"],
            promo_code="WELCOME10",
            auto_renew=True,
            payment_reference="txn-abc",
        )