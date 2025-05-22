from app.infrastructure.repositories.queue_repository import QueueRepository
from app.presentation.api.schemas.models import ServiceRegisterRequest

class QueueService:
    def __init__(self, queue_repository: QueueRepository):
        self.queue_repository = queue_repository

    def create_service_queue(self, service_type: str) -> str:
        service_exchange_name = "service.request"
        queue_name = f"service.request.{service_type}"
        routing_key = queue_name
        self.queue_repository.create_exchange(service_exchange_name, "direct")
        self.queue_repository.create_queue(queue_name)
        self.queue_repository.bind_queue_to_exchange(queue_name, service_exchange_name, routing_key)
        return queue_name


    def create_queue(self, queue_name: str) -> str:
        self.queue_repository.create_queue(queue_name)
        return queue_name
    
    def bind_queue_to_exchange(self, queue_name: str, exchange_name: str, routing_key: str) -> None:
        self.queue_repository.bind_queue_to_exchange(queue_name, exchange_name, routing_key)

    def create_fanout_exchange(self, exchange_name: str) -> None:
        self.queue_repository.create_exchange(exchange_name, "fanout")

    def create_direct_exchange(self, exchange_name: str) -> None:
        self.queue_repository.create_exchange(exchange_name, "direct")

    def create_client_exchange_bound_to_service_exchange(self, service_type: str) -> tuple[str, str]:
        client_exchange_name = "client.request"
        service_exchange_name = "service.request"
        routing_key = f"service.request.{service_type}"

        self.queue_repository.create_exchange(client_exchange_name, "fanout")
        self.queue_repository.bind_exchange_to_exchange(service_exchange_name, client_exchange_name, routing_key)
        return client_exchange_name, routing_key