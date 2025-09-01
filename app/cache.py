import redis
import json
import logging
from typing import Any, Optional
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0, decode_responses=True):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                decode_responses=decode_responses
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
        except redis.ConnectionError:
            logger.error(f"Failed to connect to Redis at {host}:{port}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(key)
            if value:
                logger.info(f"Cache HIT for key: {key}")
                return json.loads(value)
            else:
                logger.info(f"Cache MISS for key: {key}")
                return None
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            serialized_value = json.dumps(value, default=str)
            result = self.redis_client.setex(key, ttl, serialized_value)
            logger.info(f"Cache SET for key: {key} with TTL: {ttl}s")
            return result
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            result = self.redis_client.delete(key)
            logger.info(f"Cache DELETE for key: {key}")
            return bool(result)
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False
    
    def clear_all(self) -> bool:
        """Clear all cache entries"""
        try:
            self.redis_client.flushdb()
            logger.info("All cache entries cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get Redis statistics"""
        try:
            info = self.redis_client.info()
            return {
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'total_keys': sum([info.get(f'db{i}', {}).get('keys', 0) for i in range(16)])
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def get_cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio"""
        stats = self.get_stats()
        hits = stats.get('keyspace_hits', 0)
        misses = stats.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0