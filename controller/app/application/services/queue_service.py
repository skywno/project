from app.presentation.api.schemas.models import ServiceRegisterRequest, BindingRead, ExchangeRead, PublishInfo
from app.core.constants import SERVICE_REQUEST_EXCHANGE_NAME, CLIENT_REQUEST_EXCHANGE_NAME, SERVICE_RESPONSE_EXCHANGE_NAME, DATABASE_RESPONSE_QUEUE_NAME, DATABASE_REQUEST_QUEUE_NAME
from app.core.messaging.rabbitmq import RabbitMQPikaClient

from pika.exceptions import ChannelClosed
from typing import Optional

class QueueService:
    def __init__(self, rabbitmq_client: RabbitMQPikaClient):
        self.client = rabbitmq_client

    def _create_and_bind_queue(self, queue_name: str, exchange_name: str, routing_key: str) -> str:
        """Helper method to create a queue and bind it to an exchange."""
        try:
            self.client.channel.queue_declare(queue=queue_name)
            self.client.channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=routing_key)
            return queue_name
        except ChannelClosed as e:
            raise RuntimeError(f"Failed to create or bind queue {queue_name}: {str(e)}")

    def _create_exchange(self, exchange_name: str, exchange_type: str) -> None:
        """Helper method to create an exchange."""
        try:
            self.client.channel.exchange_declare(exchange=exchange_name, exchange_type=exchange_type)
        except ChannelClosed as e:
            raise RuntimeError(f"Failed to create exchange {exchange_name}: {str(e)}")

    def create_service_request_queue(self, service_type: str) -> str:
        """Creates a queue for service requests and binds it to the service request exchange."""
        queue_name = f"{SERVICE_REQUEST_EXCHANGE_NAME}.{service_type}"
        routing_key = queue_name
        self._create_exchange(SERVICE_REQUEST_EXCHANGE_NAME, "direct")
        return self._create_and_bind_queue(queue_name, SERVICE_REQUEST_EXCHANGE_NAME, routing_key)

    def create_service_response_exchange(self, service_type: str, ticket_id: int) -> PublishInfo:
        """Creates a service response exchange and sets up necessary queues."""
        exchange_name = f"{SERVICE_RESPONSE_EXCHANGE_NAME}.{service_type}"
        self._create_exchange(exchange_name, "topic")
        
        queue_name = self.get_queue_name_for_ticket(ticket_id)
        self._create_and_bind_queue(queue_name, exchange_name, queue_name)
        
        self.create_database_response_queue(exchange_name, 'ticket.#')

        return PublishInfo(
            exchange_name=exchange_name,
            routing_key=queue_name
        )
    
    def create_database_response_queue(self, exchange_name: str, routing_key: str) -> str:
        """Creates a queue for database responses and binds it to the specified exchange."""
        return self._create_and_bind_queue(DATABASE_RESPONSE_QUEUE_NAME, exchange_name, routing_key)
    
    def create_database_request_queue(self, exchange_name: str, routing_key: str) -> str:
        """Creates a queue for database requests and binds it to the specified exchange."""
        return self._create_and_bind_queue(DATABASE_REQUEST_QUEUE_NAME, exchange_name, routing_key)
    
    def get_queue_name_for_ticket(self, ticket_id: int) -> str:
        """get queue name for a ticket ID."""
        return f"ticket.{ticket_id}"

    def create_client_exchange_bound_to_service_exchange(self, service_type: str) -> PublishInfo:
        """Creates a client exchange and binds it to the service exchange."""
        routing_key = f"{SERVICE_REQUEST_EXCHANGE_NAME}.{service_type}"

        self._create_exchange(CLIENT_REQUEST_EXCHANGE_NAME, "fanout")
        try:
            self.client.channel.exchange_bind(
                destination=SERVICE_REQUEST_EXCHANGE_NAME,
                source=CLIENT_REQUEST_EXCHANGE_NAME,
                routing_key=routing_key
            )
        except ChannelClosed as e:
            raise RuntimeError(f"Failed to bind exchanges: {str(e)}")

        self.create_database_request_queue(CLIENT_REQUEST_EXCHANGE_NAME, f"{CLIENT_REQUEST_EXCHANGE_NAME}.#")
        
        return PublishInfo(
            exchange_name=CLIENT_REQUEST_EXCHANGE_NAME, 
            routing_key=routing_key
        )

