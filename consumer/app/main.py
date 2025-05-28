from fastapi import FastAPI
from app.rabbitmq import RabbitMQClient, RabbitMQConsumer
import logging
from app.client import send_register_request_and_get_queue, check_service_health
import asyncio
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

RABBITMQ_URL = os.getenv("RABBITMQ_URL") or "amqp://admin:admin@rabbitmq:5672/"

client = RabbitMQClient(RABBITMQ_URL)
consumer = RabbitMQConsumer(client)

@app.on_event("startup")
async def startup_event():
    await client.connect()
    while not await check_service_health():
        await asyncio.sleep(5)
    queue = await send_register_request_and_get_queue()
    await consumer.connect(queue)
    await consumer.start()

@app.on_event("shutdown")
async def shutdown_event():
    await consumer.stop()
    await client.close()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
def health():
    return {"status": "ok"}