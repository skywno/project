from fastapi import Depends
from app.core.messaging.rabbitmq import RabbitMQPikaClient
from app.infrastructure.repositories.queue_repository import QueueRepository, RabbitMQQueueRepository
from app.application.services.queue_service import QueueService

async def get_rabbitmq_client() -> RabbitMQPikaClient:
    host = "rabbitmq"
    port = "5672"
    username = "admin"
    password = "admin"
    return RabbitMQPikaClient(host, port, username, password)

async def get_queue_repository(rabbitmq_client: RabbitMQPikaClient = Depends(get_rabbitmq_client)) -> QueueRepository:
    return RabbitMQQueueRepository(rabbitmq_client)

async def get_queue_service(queue_repository: QueueRepository = Depends(get_queue_repository)) -> QueueService:
    return QueueService(queue_repository)