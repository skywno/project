from typing import Protocol

class QueueRepository(Protocol):
    """
    A protocol for the repository for queue operations
    """
    def create_queue(self, queue_name: str) -> None:
        """
        Create a queue
        """
        ...
    # def get_queue(self, queue_name: str) -> Queue:
    #     """
    #     Get a queue by name
    #     """
    #     ...

    def bind_queue_to_exchange(self, queue_name: str, exchange_name: str, routing_key: str) -> None:
        """
        Bind a queue to an exchange
        """
        ...

    def create_exchange(self, exchange_name: str, exchange_type: str) -> None:
        """
        Create an exchange
        """
        ...
    def bind_exchange_to_exchange(self, destination_exchange_name: str, source_exchange_name: str, routing_key: str) -> None:
        """
        Bind an exchange to another exchange
        """
        ...

from app.core.messaging.rabbitmq import RabbitMQPikaClient

class RabbitMQQueueRepository(QueueRepository):
    def __init__(self, rabbitmq_client: RabbitMQPikaClient):
        self.rabbitmq_client = rabbitmq_client

    def create_queue(self, queue_name: str) -> None:
        self.rabbitmq_client.channel.queue_declare(queue=queue_name)

    def bind_queue_to_exchange(self, queue_name: str, exchange_name: str, routing_key: str) -> None:
        self.rabbitmq_client.channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=routing_key)

    def create_exchange(self, exchange_name: str, exchange_type: str) -> None:
        self.rabbitmq_client.channel.exchange_declare(exchange=exchange_name, exchange_type=exchange_type)

    def bind_exchange_to_exchange(self, destination_exchange_name: str, source_exchange_name: str, routing_key: str) -> None:
        self.rabbitmq_client.channel.exchange_bind(destination=destination_exchange_name, source=source_exchange_name, routing_key=routing_key)