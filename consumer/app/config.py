import os

RABBITMQ_URL = os.getenv("RABBITMQ_URL") or "amqp://admin:admin@rabbitmq:5672/"
CONTROLLER_SERVICE_URL = os.getenv("CONTROLLER_SERVICE_URL") or "http://controller:8000"
CONSUMER_SERVICE_URL = os.getenv("CONSUMER_SERVICE_URL") or "http://consumer-1:8000"
SERVICE_TYPE = os.getenv("CONSUMER_TYPE") or "consumer"
