import os
from .util import get_env_boolean, get_env_int

RABBITMQ_URL = os.getenv("RABBITMQ_URL") or "amqp://admin:admin@rabbitmq:5672/"
CONTROLLER_SERVICE_URL = os.getenv("CONTROLLER_SERVICE_URL") or "http://controller:8000"
CONSUMER_SERVICE_URL = os.getenv("CONSUMER_SERVICE_URL") or "http://consumer-1:8000"
SERVICE_TYPE = os.getenv("CONSUMER_TYPE") or "consumer"


PREFETCH_COUNT = get_env_int("RABBITMQ_PREFETCH_COUNT", 10)
TIME_TO_FIRST_TOKEN = get_env_int("TIME_TO_FIRST_TOKEN", 22) # milliseconds
INTER_TOKEN_LATENCY = get_env_int("INTER_TOKEN_LATENCY", 5) # milliseconds
OUTPUT_LENGTH = get_env_int("OUTPUT_LENGTH", 115) # tokens
REQUEST_LATENCY = get_env_int("REQUEST_LATENCY", 540) # milliseconds
MAX_CONCURRENT_REQUESTS = get_env_int("MAX_CONCURRENT_REQUESTS", 5)
ENABLE_STREAMING = get_env_boolean("ENABLE_STREAMING", True)

# HTTP Client Configuration
HTTP_CONNECT_TIMEOUT = get_env_int("HTTP_CONNECT_TIMEOUT", 10)
HTTP_READ_TIMEOUT = get_env_int("HTTP_READ_TIMEOUT", 30)
