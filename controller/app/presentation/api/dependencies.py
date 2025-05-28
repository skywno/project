from fastapi import Depends
from app.core.messaging.rabbitmq import RabbitMQPikaClient
from app.application.services.queue_service import QueueService
import os
async def get_rabbitmq_client() -> RabbitMQPikaClient:
    host = os.getenv("RABBITMQ_HOST")
    port = os.getenv("RABBITMQ_PORT")
    username = os.getenv("RABBITMQ_USERNAME")
    password = os.getenv("RABBITMQ_PASSWORD")
    return RabbitMQPikaClient(host, port, username, password)


async def get_queue_service(client = Depends(get_rabbitmq_client)) -> QueueService:
    return QueueService(client)