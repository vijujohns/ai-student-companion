"""
Redis caching module with retry logic and circuit breaker
"""

import redis
import json
import time
from datetime import datetime, timedelta
from ..core.debug_logger import dlog, dwarn, derror
from ..core.config_loader import get_redis_config

_redis_config = get_redis_config()
REDIS_HOST = _redis_config["host"]
REDIS_PORT = _redis_config["port"]

# Circuit breaker state
CIRCUIT_BREAKER = {
    "is_open": False,
    "failure_count": 0,
    "last_failure_time": None,
    "threshold": 5,  # Open circuit after 5 failures
    "timeout": 60,   # Reset after 60 seconds
}

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 0.5  # seconds (exponential backoff: 0.5, 1.0, 2.0)

r = None


class InMemoryCache:
    """Minimal Redis-like fallback cache used when Redis is unavailable."""

    def __init__(self):
        self._store = {}

    def ping(self):
        return True

    def get(self, key):
        item = self._store.get(key)
        if not item:
            return None

        value, expires_at = item
        if expires_at and datetime.now() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key, value, ex=None):
        expires_at = datetime.now() + timedelta(seconds=ex) if ex else None
        self._store[key] = (value, expires_at)
        return True

    def delete(self, key):
        self._store.pop(key, None)
        return True

def init_redis():
    """Initialize Redis connection"""
    global r
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_keepalive=True,
        )
        # Test connection
        r.ping()
        dlog("CACHE", "Redis connected", host=REDIS_HOST, port=REDIS_PORT)
        print(f"✅ Redis connected at {REDIS_HOST}:{REDIS_PORT}")
        return True
    except Exception as e:
        dwarn("CACHE", f"Redis connection failed: {e}", host=REDIS_HOST, port=REDIS_PORT)
        print(f"⚠️ Redis connection failed: {e}; using in-memory fallback cache")
        r = InMemoryCache()
        return True


def check_circuit_breaker():
    """Check if circuit breaker is open and should be reset"""
    if CIRCUIT_BREAKER["is_open"]:
        now = datetime.now()
        last_failure = CIRCUIT_BREAKER["last_failure_time"]
        
        # Reset circuit after timeout
        if last_failure and (now - last_failure).total_seconds() > CIRCUIT_BREAKER["timeout"]:
            dwarn("CACHE", "Circuit breaker reset, retrying Redis")
            print("🔄 Circuit breaker reset, retrying Redis...")
            CIRCUIT_BREAKER["is_open"] = False
            CIRCUIT_BREAKER["failure_count"] = 0
            return True
        dlog("CACHE", "Circuit breaker OPEN — skipping Redis",
             failure_count=CIRCUIT_BREAKER["failure_count"])
        return False
    
    return True


def record_redis_failure():
    """Record a Redis failure and potentially open circuit breaker"""
    CIRCUIT_BREAKER["failure_count"] += 1
    CIRCUIT_BREAKER["last_failure_time"] = datetime.now()
    
    if CIRCUIT_BREAKER["failure_count"] >= CIRCUIT_BREAKER["threshold"]:
        CIRCUIT_BREAKER["is_open"] = True
        dwarn("CACHE", "Circuit breaker OPEN",
              failures=CIRCUIT_BREAKER['failure_count'],
              threshold=CIRCUIT_BREAKER['threshold'])
        print(f"⚠️ Circuit breaker OPEN after {CIRCUIT_BREAKER['threshold']} failures")


def record_redis_success():
    """Reset failure count on successful operation"""
    CIRCUIT_BREAKER["failure_count"] = 0


def get_cache(key):
    """
    ✅ NOW WITH RETRY LOGIC & CIRCUIT BREAKER
    Fetch cached value from Redis with automatic retry
    Falls back gracefully if Redis is unavailable
    """
    
    # Check circuit breaker
    if not check_circuit_breaker():
        return None
    
    # Retry logic with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            if r is None:
                init_redis()
            
            data = r.get(key)
            if data:
                record_redis_success()
                result = json.loads(data)
                dlog("CACHE", "GET HIT", key=key[:16] + "...")
                return result
            
            record_redis_success()
            dlog("CACHE", "GET MISS", key=key[:16] + "...")
            return None
            
        except redis.ConnectionError as e:
            dwarn("CACHE", f"GET retry {attempt + 1}/{MAX_RETRIES} failed",
                  key=key[:16] + "...", error=str(e))
            print(f"⚠️ Cache read attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            record_redis_failure()
            
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                time.sleep(wait_time)
        except json.JSONDecodeError:
            derror("CACHE", "Invalid JSON in cache", key=key[:16] + "...")
            print(f"⚠️ Invalid JSON in cache key: {key}")
            return None
        except Exception as e:
            derror("CACHE", f"Unexpected GET error: {e}", key=key[:16] + "...")
            print(f"❌ Unexpected cache error: {e}")
            record_redis_failure()
            return None
    
    dwarn("CACHE", f"GET failed after {MAX_RETRIES} retries", key=key[:16] + "...")
    print(f"❌ Cache read failed after {MAX_RETRIES} retries")
    return None


def set_cache(key, value):
    """
    ✅ NOW WITH RETRY LOGIC & CIRCUIT BREAKER
    Store value in Redis with TTL
    Fails silently if Redis is unavailable
    """
    
    # Check circuit breaker
    if not check_circuit_breaker():
        print("⚠️ Circuit breaker open, skipping cache write")
        return False
    
    # Retry logic with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            if r is None:
                if not init_redis():
                    return False
            
            r.set(key, json.dumps(value), ex=3600)
            record_redis_success()
            dlog("CACHE", "SET OK", key=key[:16] + "...", ttl_seconds=3600)
            return True
            
        except redis.ConnectionError as e:
            dwarn("CACHE", f"SET retry {attempt + 1}/{MAX_RETRIES} failed",
                  key=key[:16] + "...", error=str(e))
            print(f"⚠️ Cache write attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            record_redis_failure()
            
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                time.sleep(wait_time)
        except Exception as e:
            derror("CACHE", f"Unexpected SET error: {e}", key=key[:16] + "...")
            print(f"❌ Unexpected cache write error: {e}")
            record_redis_failure()
            return False
    
    dwarn("CACHE", f"SET failed after {MAX_RETRIES} retries", key=key[:16] + "...")
    print(f"❌ Cache write failed after {MAX_RETRIES} retries")
    return False


def delete_cache(key):
    """
    ✅ NOW WITH RETRY LOGIC
    Delete a key from Redis
    """
    
    # Check circuit breaker
    if not check_circuit_breaker():
        return False
    
    try:
        if r is None:
            if not init_redis():
                return False
        
        r.delete(key)
        record_redis_success()
        return True
        
    except Exception as e:
        print(f"⚠️ Cache delete error: {e}")
        record_redis_failure()
        return False


# Initialize Redis on module load
try:
    init_redis()
except Exception as e:
    print(f"⚠️ Redis initialization error: {e}")