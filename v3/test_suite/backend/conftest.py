"""
Pytest configuration and fixtures
"""

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))

# Import and initialize database before tests
from app.modules.db import init_db
from app.modules.cache import init_redis


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before running tests"""
    print("\n🔧 Setting up test environment...")
    
    try:
        init_redis()
        print("✅ Redis initialized for tests")
    except Exception as e:
        print(f"⚠️ Redis initialization failed: {e}")
    
    print("✅ Test environment ready\n")


@pytest.fixture
def clear_circuit_breaker():
    """Clear circuit breaker state between tests"""
    from app.modules.cache import CIRCUIT_BREAKER
    
    CIRCUIT_BREAKER["is_open"] = False
    CIRCUIT_BREAKER["failure_count"] = 0
    CIRCUIT_BREAKER["last_failure_time"] = None
    
    yield
    
    # Reset after test
    CIRCUIT_BREAKER["is_open"] = False
    CIRCUIT_BREAKER["failure_count"] = 0
    CIRCUIT_BREAKER["last_failure_time"] = None
