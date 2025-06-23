from aio_pika import ExchangeType, RobustChannel
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustChannel, AbstractRobustExchange, AbstractRobustQueue
from aio_pika.exceptions import ChannelClosed
from app.core.constants import SERVICE_REQUEST_EXCHANGE_NAME, CLIENT_REQUEST_EXCHANGE_NAME, SERVICE_RESPONSE_EXCHANGE_NAME, DATABASE_RESPONSE_QUEUE_NAME, DATABASE_REQUEST_QUEUE_NAME
from app.messaging.core import RabbitMQClient
from app.keda.service import KedaService
from app.messaging.models import PublishInfo
import logging

logger = logging.getLogger(__name__)


class RabbitMQKedaService:
    def __init__(self, rabbitmq_client: RabbitMQClient, keda_service: KedaService):
        self.queue_created_queue_name = "queue_created"
        self.keda_service = keda_service
        self.rabbitmq_client = rabbitmq_client

    async def start_consuming_to_queue_created_events(self):
        exchange_name = "amq.rabbitmq.event"
        routing_key = "queue.created"
        connection = await self.rabbitmq_client.connect()
        try:
            channel = await connection.channel()
            # This exchange will be created by RabbitMQ plugin for event notifications
            # exchange = await channel.declare_exchange(exchange_name, type=ExchangeType.TOPIC, durable=True)
            exchange = await channel.get_exchange(exchange_name, ensure=True)
            queue = await channel.declare_queue(self.queue_created_queue_name, durable=True)
            await queue.bind(exchange, routing_key)
            await queue.consume(self.on_message, no_ack=False)
            logger.info(f"Consuming to queue created events on {self.queue_created_queue_name}")
        except Exception as e:
            logger.error(f"Error starting consuming to queue created events: {e}")
            
    async def on_message(self, message: AbstractIncomingMessage):
        queue_name = message.headers.get("name")
        managed_objects = self.keda_service.get_managed_scaled_objects()
        if queue_name not in managed_objects:
            logger.info(f"New RabbitMQ queue detected: '{queue_name}'.")
            target_deployment = self.get_target_deployment_name(queue_name)
            if target_deployment:
                self.keda_service.create_scaled_object(queue_name, target_deployment, logger)
        else:
            logger.debug(f"Queue '{queue_name}' already has a managed ScaledObject.")
        await message.ack()

    def get_target_deployment_name(self, queue_name: str) -> str | None:
        """Map a queue name to a target deployment name."""
        if queue_name.startswith(SERVICE_REQUEST_EXCHANGE_NAME):
            return queue_name.removeprefix(SERVICE_REQUEST_EXCHANGE_NAME + '.')
        logger.warning(f"No specific mapping rule for queue '{queue_name}'. Skipping creation.")
        return None

    async def stop_consuming(self):
        await self.rabbitmq_client.disconnect()

class QueueService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            if cls._instance is None:
                cls._instance = super(QueueService, cls).__new__(cls)
        return cls._instance

    def __init__(self, rabbitmq_client: RabbitMQClient):
        if not hasattr(self, 'initialized'):
            self.client = rabbitmq_client
            self._channel: AbstractRobustChannel | None = None
            self._service_request_exchange: AbstractRobustExchange | None = None
            self.initialized = True
        else:
            logger.debug("QueueService already initialized")

    async def channel(self) -> RobustChannel:
        if not self._channel:
            logger.info(f"Creating new channel")
            await self.client.connect()
            self._channel = await self.client.connection.channel()
            logger.info(f"Created channel")
        return self._channel

    async def create_service_request_queue(self, service_type: str) -> AbstractRobustQueue:
        """Creates a queue for service requests and binds it to the service request exchange."""
        queue_name = f"{SERVICE_REQUEST_EXCHANGE_NAME}.{service_type}"
        routing_key = queue_name
        self._service_request_exchange = await self._create_exchange(SERVICE_REQUEST_EXCHANGE_NAME, "direct")
        logger.info(f"Created service request exchange {SERVICE_REQUEST_EXCHANGE_NAME}")
        return await self._create_and_bind_queue(queue_name, self._service_request_exchange, routing_key)

    async def create_service_response_exchange(self, service_type: str, ticket_id: int) -> PublishInfo:
        """Creates a service response exchange and sets up necessary queues."""
        exchange_name = f"{SERVICE_RESPONSE_EXCHANGE_NAME}.{service_type}"
        queue = await self.get_queue_for_ticket(ticket_id)
        routing_key = queue.name
        service_response_exchange = await self._create_exchange(exchange_name, "topic")
        await queue.bind(service_response_exchange, routing_key)
        logger.info(f"Created and bound queue {queue.name} to {service_response_exchange} with routing key {routing_key}")
        await self._create_database_response_queue(service_response_exchange, 'ticket.#')

        return PublishInfo(
            exchange_name=exchange_name,
            routing_key=routing_key
        )
        
    async def get_queue_for_ticket(self, ticket_id: int) -> AbstractRobustQueue:
        """get queue name for a ticket ID."""
        queue_name = f"ticket.{ticket_id}"
        channel = await self.channel()
        queue = await channel.declare_queue(queue_name, durable=True, auto_delete=True)
        return queue

    async def create_client_exchange_bound_to_service_exchange(self, service_type: str) -> PublishInfo:
        """Creates a client exchange and binds it to the service exchange."""
        routing_key = f"{SERVICE_REQUEST_EXCHANGE_NAME}.{service_type}"

        client_exchange = await self._create_exchange(CLIENT_REQUEST_EXCHANGE_NAME, "fanout")
        await self._service_request_exchange.bind(client_exchange, routing_key) # destination_exchange.bind(source_exchange, routing_key)
        await self._create_database_request_queue(client_exchange, f"{CLIENT_REQUEST_EXCHANGE_NAME}.#")
        
        return PublishInfo(
            exchange_name=CLIENT_REQUEST_EXCHANGE_NAME, 
            routing_key=routing_key
        )

    async def _create_database_response_queue(self, source_exchange: AbstractRobustExchange, routing_key: str) -> str:
        """Creates a queue for database responses and binds it to the specified exchange."""
        return await self._create_and_bind_queue(DATABASE_RESPONSE_QUEUE_NAME, source_exchange, routing_key)
    
    async def _create_database_request_queue(self, source_exchange: AbstractRobustExchange, routing_key: str) -> str:
        """Creates a queue for database requests and binds it to the specified exchange."""
        return await self._create_and_bind_queue(DATABASE_REQUEST_QUEUE_NAME, source_exchange, routing_key)

    async def _create_exchange(self, exchange_name: str, exchange_type: str) -> AbstractRobustExchange:
        """Helper method to create an exchange."""
        try:
            channel = await self.channel()
            exchange: AbstractRobustExchange = await channel.declare_exchange(
                name=exchange_name, 
                type=exchange_type, 
                durable=True)
            return exchange
        except ChannelClosed as e:
            raise RuntimeError(f"Failed to create exchange {exchange_name}: {str(e)}")

    async def _create_and_bind_queue(self, queue_name: str, source_exchange: AbstractRobustExchange, routing_key: str) -> AbstractRobustQueue:
        """Helper method to create a queue and bind it to an exchange."""
        try:
            channel = await self.channel()
            queue: AbstractRobustQueue = await channel.declare_queue(
                name=queue_name, 
                durable=True)
            await queue.bind(source_exchange, routing_key)
            logger.info(f"Created and bound queue {queue_name} to {source_exchange} with routing key {routing_key}")
            return queue
        except ChannelClosed as e:
            raise RuntimeError(f"Failed to create or bind queue {queue_name}: {str(e)}")
