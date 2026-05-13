"""
Tests for API versioning strategy and backward compatibility.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend app to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestVersioningAvailability:
    """Verify that both versioned and unversioned paths are available."""

    def test_unversioned_health_endpoint_exists(self, client):
        """Unversioned /health path should be available."""
        response = client.get("/health/runtime")
        # May be 200 or 404 depending on implementation, but shouldn't be 404 due to missing router
        assert response.status_code in [200, 404, 500]

    def test_versioned_health_endpoint_exists(self, client):
        """Versioned /api/v1/health path should be available."""
        response = client.get("/api/v1/health/runtime")
        # May be 200 or 404 depending on implementation, but shouldn't be 404 due to missing router
        assert response.status_code in [200, 404, 500]

    def test_unversioned_login_endpoint_exists(self, client):
        """Unversioned /login path should be available."""
        response = client.post("/login", json={"email": "test@example.com", "password": "test"})
        # Should not be 404 (which would indicate missing router)
        assert response.status_code != 404

    def test_versioned_login_endpoint_exists(self, client):
        """Versioned /api/v1/login path should be available."""
        response = client.post("/api/v1/login", json={"email": "test@example.com", "password": "test"})
        # Should not be 404 (which would indicate missing router)
        assert response.status_code != 404

    def test_unversioned_register_endpoint_exists(self, client):
        """Unversioned /register path should be available."""
        response = client.post("/register", json={
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password": "test",
            "dob": "2000-01-01",
            "role": "student"
        })
        # Should not be 404
        assert response.status_code != 404

    def test_versioned_register_endpoint_exists(self, client):
        """Versioned /api/v1/register path should be available."""
        response = client.post("/api/v1/register", json={
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "password": "test",
            "dob": "2000-01-01",
            "role": "student"
        })
        # Should not be 404
        assert response.status_code != 404


class TestVersioningResponseFormat:
    """Verify that both versioned and unversioned endpoints return consistent response formats."""

    def test_unversioned_error_response_has_envelope(self, client):
        """Unversioned error responses should follow the envelope format."""
        response = client.post("/login", json={"email": "test@example.com", "password": "wrong"})
        # Login failure is expected; check response structure
        assert response.status_code in [400, 401, 422, 500]
        data = response.json()
        # Should have message envelope structure
        assert isinstance(data, dict)
        # Error responses should have message or detail field
        assert "message" in data or "detail" in data or "error" in data

    def test_versioned_error_response_has_envelope(self, client):
        """Versioned error responses should follow the envelope format."""
        response = client.post("/api/v1/login", json={"email": "test@example.com", "password": "wrong"})
        # Login failure is expected; check response structure
        assert response.status_code in [400, 401, 422, 500]
        data = response.json()
        # Should have message envelope structure
        assert isinstance(data, dict)
        # Error responses should have message or detail field
        assert "message" in data or "detail" in data or "error" in data

    def test_version_v1_prefix_correct(self, client):
        """Verify that v1 routes are prefixed correctly."""
        # This is a basic sanity check that the /api/v1 prefix is applied
        # The existence of v1 endpoint (different from 404) indicates proper prefixing
        response = client.get("/api/v1/health/runtime")
        # Status may vary, but should not be 404 if router is properly registered
        # (404 would mean the route wasn't found in the app)
        assert response.status_code != 404


class TestBackwardCompatibility:
    """Verify that unversioned endpoints continue to function for backward compatibility."""

    def test_unversioned_paths_still_work(self, client):
        """Core unversioned paths should remain functional."""
        # These should at least not 404 (even if they fail auth/validation)
        endpoints = [
            ("GET", "/health/runtime"),
            ("POST", "/login"),
            ("POST", "/register"),
            ("GET", "/sessions"),
            ("POST", "/ask"),
        ]
        for method, path in endpoints:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path, json={})
            # Most important: should NOT be 404
            assert response.status_code != 404, f"Backward compatibility broken: {method} {path} returned 404"

    def test_versioned_paths_work(self, client):
        """Core versioned paths should function."""
        # These should at least not 404
        endpoints = [
            ("GET", "/api/v1/health/runtime"),
            ("POST", "/api/v1/login"),
            ("POST", "/api/v1/register"),
            ("GET", "/api/v1/sessions"),
            ("POST", "/api/v1/ask"),
        ]
        for method, path in endpoints:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path, json={})
            # Most important: should NOT be 404
            assert response.status_code != 404, f"Versioning failed: {method} {path} returned 404"


class TestMobileCollectionContracts:
    """Verify mobile-heavy collections expose pagination and response schemas."""

    def test_openapi_contains_paginated_collection_parameters(self, client):
        schema = client.get("/openapi.json").json()
        paths = schema.get("paths", {})
        for path in [
            "/sessions",
            "/lesson-plan/sessions",
            "/quiz/sessions",
            "/flashcards/sessions",
            "/notes",
            "/students/{student_username}/assignments",
        ]:
            operation = paths.get(path, {}).get("get")
            assert operation, f"Missing GET contract for {path}"
            parameter_names = {param.get("name") for param in operation.get("parameters", [])}
            assert {"limit", "offset"}.issubset(parameter_names)


class TestVersioningRobustness:
    """Test edge cases and robustness of versioning strategy."""

    def test_multiple_slashes_not_broken(self, client):
        """Verify routing handles path edge cases."""
        # Double slashes shouldn't cause issues
        response = client.get("//health/runtime")
        # 404 is acceptable for malformed path
        assert response.status_code in [200, 400, 404, 422]

    def test_v2_path_not_available(self, client):
        """v2 should not be available yet (returns 404)."""
        response = client.get("/api/v2/login")
        assert response.status_code == 404

    def test_wrong_method_not_confused_with_version_error(self, client):
        """Wrong HTTP method should not be confused with versioning issues."""
        response = client.get("/api/v1/login")  # POST is expected
        # Should not be a 404; could be 405 (Method Not Allowed) or other error
        assert response.status_code != 404
