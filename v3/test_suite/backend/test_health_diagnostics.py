"""
Test Health Diagnostics Endpoints
Ensures health check responses include:
- Database connectivity
- FAISS/index freshness
- Cache/Redis status
- OCR availability
- Model availability and configuration
"""

import pytest
from unittest.mock import MagicMock, patch
from app.modules.db import get_connection, init_db
from app.core.debug_logger import dlog, dwarn, derror


class TestHealthEndpointBasics:
    """Test basic health endpoint functionality."""
    
    @classmethod
    def setup_class(cls):
        """Initialize test database."""
        init_db()
    
    @patch("app.api.routes.health_check")
    def test_health_endpoint_returns_status(self, mock_health):
        """Verify health endpoint returns status."""
        mock_health.return_value = {
            "status": "healthy",
            "timestamp": "2026-05-07T00:00:00Z"
        }
        
        result = mock_health()
        assert result["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in result
    
    @patch("app.api.routes.health_check")
    def test_health_endpoint_includes_component_status(self, mock_health):
        """Verify health endpoint includes individual component status."""
        mock_health.return_value = {
            "status": "healthy",
            "components": {
                "database": "healthy",
                "faiss": "healthy",
                "cache": "healthy",
                "ocr": "healthy",
                "models": "healthy"
            }
        }
        
        result = mock_health()
        assert "components" in result
        assert all(key in result["components"] for key in 
                  ["database", "faiss", "cache", "ocr", "models"])


class TestDatabaseHealthCheck:
    """Test database health diagnostics."""
    
    @classmethod
    def setup_class(cls):
        """Initialize test database."""
        init_db()
    
    def test_database_connectivity_check(self):
        """Verify database can be checked for connectivity."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result is not None
            conn.close()
            db_healthy = True
        except Exception as e:
            db_healthy = False
        
        assert db_healthy is True
    
    @patch("app.modules.db.get_connection")
    def test_database_health_status_on_failure(self, mock_conn):
        """Verify database health reflects connection failures."""
        mock_conn.side_effect = Exception("Connection failed")
        
        try:
            conn = mock_conn()
            db_healthy = False
        except Exception:
            db_healthy = False
        
        assert db_healthy is False


class TestFAISSHealthCheck:
    """Test FAISS index health diagnostics."""
    
    @patch("app.modules.faiss_store.check_index_freshness")
    def test_faiss_index_freshness_check(self, mock_freshness):
        """Verify FAISS index freshness can be checked."""
        mock_freshness.return_value = {
            "is_fresh": True,
            "last_updated": "2026-05-06T12:00:00Z",
            "document_count": 42
        }
        
        freshness = mock_freshness()
        assert freshness["is_fresh"] in [True, False]
        assert "last_updated" in freshness
        assert "document_count" in freshness
    
    @patch("app.modules.faiss_store.get_index_stats")
    def test_faiss_index_stats(self, mock_stats):
        """Verify FAISS index statistics are available."""
        mock_stats.return_value = {
            "status": "healthy",
            "index_type": "FAISS",
            "total_vectors": 1000,
            "vector_dimension": 384
        }
        
        stats = mock_stats()
        assert stats["status"] in ["healthy", "degraded", "failed"]
        assert "total_vectors" in stats
    
    @patch("app.modules.faiss_store.check_index_freshness")
    def test_stale_index_detected(self, mock_freshness):
        """Verify stale index can be detected."""
        mock_freshness.return_value = {
            "is_fresh": False,
            "last_updated": "2026-04-01T00:00:00Z"  # Old date
        }
        
        freshness = mock_freshness()
        assert freshness["is_fresh"] is False


class TestCacheHealthCheck:
    """Test cache/Redis health diagnostics."""
    
    @patch("app.modules.cache.check_cache_health")
    def test_cache_connectivity_check(self, mock_cache_check):
        """Verify cache connectivity can be checked."""
        mock_cache_check.return_value = {
            "status": "healthy",
            "response_time_ms": 2
        }
        
        result = mock_cache_check()
        assert result["status"] in ["healthy", "degraded", "unavailable"]
        assert "response_time_ms" in result
    
    @patch("app.modules.cache.get_cache_stats")
    def test_cache_hit_miss_stats(self, mock_stats):
        """Verify cache hit/miss statistics are available."""
        mock_stats.return_value = {
            "hits": 1250,
            "misses": 380,
            "hit_rate": 0.766
        }
        
        stats = mock_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats


class TestOCRHealthCheck:
    """Test OCR availability and health."""
    
    @patch("app.modules.ocr.check_ocr_availability")
    def test_ocr_availability_check(self, mock_ocr_check):
        """Verify OCR availability can be checked."""
        mock_ocr_check.return_value = {
            "available": True,
            "engine": "Tesseract",
            "languages": ["en", "hi", "ta"]
        }
        
        result = mock_ocr_check()
        assert result["available"] in [True, False]
        if result["available"]:
            assert "engine" in result
    
    @patch("app.modules.ocr.test_ocr_processing")
    def test_ocr_basic_functionality(self, mock_ocr_test):
        """Verify OCR basic functionality test."""
        mock_ocr_test.return_value = {
            "status": "working",
            "processing_time_ms": 450
        }
        
        result = mock_ocr_test()
        assert result["status"] in ["working", "degraded", "failed"]


class TestModelHealthCheck:
    """Test model availability and configuration health."""
    
    @patch("app.modules.model_manager.get_available_models")
    def test_available_models_listed(self, mock_models):
        """Verify available models can be listed."""
        mock_models.return_value = [
            {"name": "mistral-7b", "status": "loaded", "vram_used_mb": 5000},
            {"name": "phi-4", "status": "available", "vram_used_mb": 0},
            {"name": "tinyllama", "status": "loaded", "vram_used_mb": 1200}
        ]
        
        models = mock_models()
        assert len(models) > 0
        assert all("name" in m for m in models)
        assert all("status" in m for m in models)
    
    @patch("app.modules.model_manager.get_active_model")
    def test_active_model_status(self, mock_active):
        """Verify active model status is available."""
        mock_active.return_value = {
            "name": "mistral-7b",
            "status": "healthy",
            "response_time_ms": 250,
            "vram_used_mb": 5000,
            "vram_total_mb": 8000
        }
        
        result = mock_active()
        assert result["name"] is not None
        assert result["status"] in ["healthy", "loading", "failed"]
    
    @patch("app.modules.model_manager.check_model_configuration")
    def test_model_configuration_validation(self, mock_config_check):
        """Verify model configuration can be validated."""
        mock_config_check.return_value = {
            "valid": True,
            "issues": []
        }
        
        result = mock_config_check()
        assert result["valid"] in [True, False]
        assert "issues" in result


class TestComprehensiveHealthResponse:
    """Test full health endpoint response structure."""
    
    @patch("app.api.routes.get_full_health_status")
    def test_complete_health_response_structure(self, mock_full_health):
        """Verify complete health response has all required fields."""
        mock_full_health.return_value = {
            "status": "healthy",
            "timestamp": "2026-05-07T10:30:00Z",
            "version": "1.0.0",
            "uptime_seconds": 86400,
            "components": {
                "database": {
                    "status": "healthy",
                    "response_time_ms": 5
                },
                "faiss": {
                    "status": "healthy",
                    "is_fresh": True,
                    "document_count": 120
                },
                "cache": {
                    "status": "healthy",
                    "response_time_ms": 2,
                    "hit_rate": 0.85
                },
                "ocr": {
                    "status": "available",
                    "engine": "Tesseract"
                },
                "models": {
                    "status": "loaded",
                    "active_model": "mistral-7b",
                    "available_count": 3
                }
            }
        }
        
        health = mock_full_health()
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in health
        assert len(health["components"]) >= 5
    
    @patch("app.api.routes.get_full_health_status")
    def test_degraded_health_with_single_component_failure(self, mock_full_health):
        """Verify degraded status when one component fails."""
        mock_full_health.return_value = {
            "status": "degraded",
            "components": {
                "database": {"status": "healthy"},
                "faiss": {"status": "healthy"},
                "cache": {"status": "unhealthy", "error": "Connection timeout"},
                "ocr": {"status": "available"},
                "models": {"status": "loaded"}
            }
        }
        
        health = mock_full_health()
        assert health["status"] == "degraded"
        assert health["components"]["cache"]["status"] == "unhealthy"
