"""
Redis caching module
"""

import redis
import json

# Use your working WSL IP
#r = redis.Redis(host="172.25.226.149", port=6379, decode_responses=True)
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def get_cache(key):
    """
    Fetch cached value from Redis
    """
    try:
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"❌ Cache read error: {e}")

    return None


def set_cache(key, value):
    """
    Store value in Redis with TTL
    """
    try:
        r.set(key, json.dumps(value), ex=3600)
    except Exception as e:
        print(f"❌ Cache write error: {e}")