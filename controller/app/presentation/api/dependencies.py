from fastapi import Depends
from app.core.messaging.rabbitmq import RabbitMQPikaClient
from app.application.services.queue_service import QueueService

async def get_rabbitmq_client() -> RabbitMQPikaClient:
    host = "rabbitmq"
    port = "5672"
    username = "admin"
    password = "admin"
    return RabbitMQPikaClient(host, port, username, password)


async def get_queue_service(client = Depends(get_rabbitmq_client)) -> QueueService:
    return QueueService(client)