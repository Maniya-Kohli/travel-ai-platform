import redis
import json
import asyncio

class QueueConsumer:
    def __init__(self, redis_url):
        # Decode responses and use asyncio-compatible redis client
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

    async def pop(self, queue_name):
        # Blocking pop with timeout
        while True:
            result = self.redis.blpop(queue_name, timeout=2)
            if result:
                _, value = result
                try:
                    return json.loads(value)
                except Exception:
                    return value
            await asyncio.sleep(1)
