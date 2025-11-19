import redis
import os

class RedisClient:
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6381))
        self.client = redis.StrictRedis(host=self.host, port=self.port, decode_responses=True)

    def set(self, key, value):
        self.client.set(key, value)

    def get(self, key):
        return self.client.get(key)

    def delete(self, key):
        self.client.delete(key)

# Example usage
if __name__ == "__main__":
    redis_client = RedisClient()
    redis_client.set("test_key", "test_value")
    print(redis_client.get("test_key"))