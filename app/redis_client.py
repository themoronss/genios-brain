import redis
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# If it's an upstash redis URL or uses TLS (rediss://), we need ssl_cert_reqs="none"
if redis_url.startswith("rediss://"):
    redis_client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs="none")
else:
    redis_client = redis.from_url(redis_url, decode_responses=True)