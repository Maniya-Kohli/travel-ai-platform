import redis
import json

class QueueProducer:
    def __init__(self, redis_url):
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def push(self, queue_name, item):
        self.redis.lpush(queue_name, json.dumps(item))
