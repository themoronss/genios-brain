import redis
import os
from dotenv import load_dotenv

load_dotenv()

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)