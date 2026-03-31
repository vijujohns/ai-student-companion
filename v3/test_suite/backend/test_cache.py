"""
Test Cache Retry Logic & Circuit Breaker (Issue #8)
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from app.modules.cache import get_cache, set_cache, delete_cache, CIRCUIT_BREAKER, init_redis


class TestCacheRetryLogic:
    """Test cache retry logic with circuit breaker"""
    
    def test_init_redis_success(self):
        """Redis initialization should succeed on normal connection"""
        result = init_redis()
        assert result == True
    
    def test_get_cache_miss(self):
        """Cache miss should return None gracefully"""
        result = get_cache("nonexistent-key-12345")
        assert result is None
    
    def test_set_get_cache_roundtrip(self):
        """Set and get cache should work"""
        test_key = "test-key-roundtrip"
        test_value = {"name": "test", "value": 123}
        
        # Set cache
        set_result = set_cache(test_key, test_value)
        assert set_result == True
        
        # Get cache
        retrieved = get_cache(test_key)
        assert retrieved == test_value
    
    def test_delete_cache(self):
        """Delete cache should work"""
        test_key = "test-key-delete"
        test_value = {"data": "test"}
        
        # Set cache
        set_cache(test_key, test_value)
        
        # Verify it exists
        assert get_cache(test_key) == test_value
        
        # Delete it
        delete_result = delete_cache(test_key)
        assert delete_result == True
        
        # Verify it's gone
        assert get_cache(test_key) is None
    
    @patch('app.modules.cache.r')
    def test_get_cache_connection_error(self, mock_redis):
        """Cache should gracefully handle connection errors"""
        # Simulate connection error
        mock_redis.get.side_effect = Exception("Connection refused")
        
        # Should return None instead of crashing
        result = get_cache("test-key")
        assert result is None
    
    @patch('app.modules.cache.r')
    def test_set_cache_connection_error(self, mock_redis):
        """Set cache should handle connection errors gracefully"""
        # Simulate connection error
        mock_redis.set.side_effect = Exception("Connection refused")
        
        # Should return False instead of crashing
        result = set_cache("test-key", {"data": "test"})
        assert result == False
    
    def test_circuit_breaker_state(self):
        """Circuit breaker state should be accessible"""
        assert "is_open" in CIRCUIT_BREAKER
        assert "failure_count" in CIRCUIT_BREAKER
        assert "threshold" in CIRCUIT_BREAKER
        assert "timeout" in CIRCUIT_BREAKER


class TestJsonCacheData:
    """Test cache with various JSON data types"""
    
    def test_cache_dict(self):
        """Cache should handle dictionaries"""
        key = "test-dict"
        value = {"name": "John", "age": 30, "nested": {"key": "value"}}
        
        set_cache(key, value)
        retrieved = get_cache(key)
        assert retrieved == value
    
    def test_cache_list(self):
        """Cache should handle lists"""
        key = "test-list"
        value = [1, 2, 3, "four", {"five": 5}]
        
        set_cache(key, value)
        retrieved = get_cache(key)
        assert retrieved == value
    
    def test_cache_string(self):
        """Cache should handle strings"""
        key = "test-string"
        value = "Hello, World!"
        
        set_cache(key, value)
        retrieved = get_cache(key)
        assert retrieved == value
    
    def test_cache_number(self):
        """Cache should handle numbers"""
        key = "test-number"
        value = 42
        
        set_cache(key, value)
        retrieved = get_cache(key)
        assert retrieved == value
    
    def test_cache_boolean(self):
        """Cache should handle booleans"""
        key = "test-bool"
        value = True
        
        set_cache(key, value)
        retrieved = get_cache(key)
        assert retrieved == value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
