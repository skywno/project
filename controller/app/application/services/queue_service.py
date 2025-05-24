from app.presentation.api.schemas.models import ServiceRegisterRequest, BindingRead, ExchangeRead, PublishInfo
from app.core.constants import SERVICE_REQUEST_EXCHANGE_NAME, CLIENT_REQUEST_EXCHANGE_NAME, SERVICE_RESPONSE_EXCHANGE_NAME
from app.core.messaging.rabbitmq import RabbitMQPikaClient

class QueueService:
    def __init__(self, rabbitmq_client: RabbitMQPikaClient):
        self.client = rabbitmq_client

    def create_service_request_queue(self, service_type: str) -> str:
        # Routing key is the same as the queue name
        queue_name = f"{SERVICE_REQUEST_EXCHANGE_NAME}.{service_type}"
        routing_key = queue_name
        self.client.channel.exchange_declare(exchange=SERVICE_REQUEST_EXCHANGE_NAME, exchange_type="direct")
        self.client.channel.queue_declare(queue=queue_name)
        self.client.channel.queue_bind(queue=queue_name, exchange=SERVICE_REQUEST_EXCHANGE_NAME, routing_key=routing_key)
        return queue_name

    def create_service_response_exchange(self, service_type: str, ticket_id: int) -> PublishInfo:
        exchange_name = f"{SERVICE_RESPONSE_EXCHANGE_NAME}.{service_type}"
        self.client.channel.exchange_declare(exchange=exchange_name, exchange_type="topic")
        queue_name = self.create_queue_for_ticket(ticket_id)
        self.client.channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=queue_name)
        return PublishInfo(
            exchange_name=exchange_name,
            routing_key=queue_name
        )
    
    def create_queue_for_ticket(self, ticket_id: int) -> str:
        queue_name = f"ticket.{ticket_id}"
        self.client.channel.queue_declare(queue=queue_name)
        return queue_name

    def create_client_exchange_bound_to_service_exchange(self, service_type: str) -> PublishInfo:
        # TODO: Check if the service type is available, meaning that the service is listening to the service queue.
        # TODO: check if the exchange already exist for the service type.
        # TODO: need to check if there is any queue bound to the service exchange? 

        # Routing key will be propagated to the service exchange
        routing_key = f"{SERVICE_REQUEST_EXCHANGE_NAME}.{service_type}"

        self.client.channel.exchange_declare(exchange=CLIENT_REQUEST_EXCHANGE_NAME, exchange_type="fanout")
        self.client.channel.exchange_bind(destination=SERVICE_REQUEST_EXCHANGE_NAME, source=CLIENT_REQUEST_EXCHANGE_NAME, routing_key=routing_key)
        return PublishInfo(
            exchange_name=CLIENT_REQUEST_EXCHANGE_NAME, 
            routing_key=routing_key
        )

