from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
import asyncio
import os

from app.client import send_register_request_and_get_queue, check_service_health
from app.rabbitmq import RabbitMQClient, RabbitMQConsumer


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = RabbitMQClient()
    consumer = RabbitMQConsumer(client)
    await client.connect()
    while not await check_service_health():
        logger.info("Waiting for controller service to be ready")
        await asyncio.sleep(10)
    try:
        queue = await send_register_request_and_get_queue()
        await consumer.connect(queue)
        await consumer.start()
    except Exception as e:
        logger.error(f"Error subscribing to queue: {e}")
    yield
    await consumer.stop()
    await client.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
def health():
    return {"status": "ok"}