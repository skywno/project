from fastapi import Depends

from app.core.config import get_settings

from app.messaging.core import RabbitMQClient
from app.kubernetes.core import KubernetesClient

from app.keda.service import KedaService
from app.messaging.service import QueueService, RabbitMQKedaService
import logging

logger = logging.getLogger(__name__)

_rabbitmq_client : RabbitMQClient | None = None

async def get_rabbitmq_client() -> RabbitMQClient:
    global _rabbitmq_client
    if not _rabbitmq_client:
        settings = get_settings()
        host = settings.rabbitmq_host
        port = settings.rabbitmq_port
        username = settings.rabbitmq_username
        password = settings.rabbitmq_password
        _rabbitmq_client = RabbitMQClient(host, port, username, password)
        logger.info("Creating new RabbitMQ client")
    await _rabbitmq_client.connect()
    return _rabbitmq_client


def get_queue_service(client = Depends(get_rabbitmq_client)) -> QueueService:
    return QueueService(client)

async def get_rabbitmq_keda_service() -> RabbitMQKedaService:
    k8s_client = KubernetesClient()
    keda_service = KedaService(k8s_client)
    rabbitmq_client = await get_rabbitmq_client()
    return RabbitMQKedaService(rabbitmq_client, keda_service)