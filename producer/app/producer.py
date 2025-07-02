#!/usr/bin/env python
import pika
import logging
import asyncio
from typing import Optional
from pika.spec import BasicProperties
from pika.adapters.asyncio_connection import AsyncioConnection
from app.config import RABBITMQ_HOST, RABBITMQ_USERNAME, RABBITMQ_PASSWORD

logger = logging.getLogger(__name__)

class RabbitMQProducerException(Exception):
    pass

class AsyncRabbitMQProducer:
    """Async RabbitMQ producer with connection pooling and non-blocking operations."""
    
    def __init__(self, host: str = RABBITMQ_HOST, username: str = RABBITMQ_USERNAME, password: str = RABBITMQ_PASSWORD):
        self.host = host
        self.credentials = pika.PlainCredentials(username, password)
        self._connection: Optional[AsyncioConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._lock = asyncio.Lock()
        self._connection_ready = asyncio.Event()
        self._closing = False

    async def ensure_connection(self) -> None:
        """Ensure connection is established."""
        if self._connection and self._connection.is_open:
            return
            
        async with self._lock:
            if self._connection and self._connection.is_open:
                return
                
            try:
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    credentials=self.credentials,
                    heartbeat=60
                )
                
                self._connection = AsyncioConnection(
                    parameters=parameters,
                    on_open_callback=self._on_connection_open,
                    on_open_error_callback=self._on_connection_open_error,
                    on_close_callback=self._on_connection_closed
                )
                
                # Wait for connection to be ready
                await asyncio.wait_for(self._connection_ready.wait(), timeout=5.0)
                logger.info(f"Connected to RabbitMQ at {self.host}")
                
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise RabbitMQProducerException(f"Failed to connect to RabbitMQ: {e}")

    def _on_connection_open(self, connection: AsyncioConnection) -> None:
        """Called when connection is opened."""
        logger.info("RabbitMQ connection opened")
        self._connection = connection
        self._open_channel()

    def _on_connection_open_error(self, connection: AsyncioConnection, err: Exception) -> None:
        """Called when connection fails to open."""
        logger.error(f"RabbitMQ connection failed: {err}")
        self._connection_ready.set()  # Unblock waiting tasks

    def _on_connection_closed(self, connection: AsyncioConnection, reason: Exception) -> None:
        """Called when connection is closed."""
        logger.warning(f"RabbitMQ connection closed: {reason}")
        self._connection = None
        self._channel = None
        self._connection_ready.clear()

    def _open_channel(self) -> None:
        """Open a new channel."""
        if self._connection:
            self._connection.channel(on_open_callback=self._on_channel_open)

    def _on_channel_open(self, channel: pika.channel.Channel) -> None:
        """Called when channel is opened."""
        logger.info("RabbitMQ channel opened")
        self._channel = channel
        self._connection_ready.set()

    async def send_message(self, exchange: str, client_id: str, ticket_id: str, routing_key: str, body: str) -> None:
        """Send a message asynchronously."""
        await self.ensure_connection()
        
        if not self._channel:
            raise RabbitMQProducerException("Channel not available")
        
        try:
            properties = BasicProperties(
                headers={
                    "x-ticket-id": ticket_id,
                    "x-client-id": client_id,
                    "event_type": "request",
                    "user_id": "some user_id",
                    "group_id": "some group id",
                    "target_type": "consumer"
                }
            )
            
            # Use asyncio.run_in_executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._channel.basic_publish,
                exchange,
                routing_key,
                body,
                properties
            )
            logger.info(f" [x] Sent message: {body}")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise RabbitMQProducerException(f"Failed to send message: {e}")

    async def close(self) -> None:
        """Close the connection."""
        self._closing = True
        if self._channel:
            self._channel.close()
        if self._connection and self._connection.is_open:
            self._connection.close()

# Keep the original blocking producer for backward compatibility
class RabbitMQProducer:
    _instance = None
    _initialized = False
    
    def __new__(cls, host: str = RABBITMQ_HOST, username: str = RABBITMQ_USERNAME, password: str = RABBITMQ_PASSWORD):
        if cls._instance is None:
            cls._instance = super(RabbitMQProducer, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, host: str = RABBITMQ_HOST, username: str = RABBITMQ_USERNAME, password: str = RABBITMQ_PASSWORD):
        if not self._initialized:
            self.host = host
            self.connection : pika.BlockingConnection | None = None
            self.channel : pika.BlockingChannel | None = None
            self.credentials = pika.PlainCredentials(username, password)
            self._initialized = True

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Don't close the connection in context manager for singleton
        pass

    def connect(self) -> None:
        """Establish connection to RabbitMQ server."""
        if self.connection and self.connection.is_open:
            logger.info(f"Already connected to RabbitMQ at {self.host}")
            return
            
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, credentials=self.credentials)
            )
            self.channel = self.connection.channel()
            logger.info(f"Connected to RabbitMQ at {self.host}")
            
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise RabbitMQProducerException(f"Failed to connect to RabbitMQ: {e}")

    def send_message(self, exchange: str, client_id: str, ticket_id: str, routing_key: str, body: str) -> None:
        """Send a message to the specified queue."""
        if not self.connection or not self.channel or not self.connection.is_open:
            self.connect()
        
        try:
            properties = BasicProperties(
                headers={
                    "x-ticket-id": ticket_id,
                    "x-client-id": client_id,
                    "event_type": "request",
                    "user_id": "some user_id",
                    "group_id": "some group id",
                    "target_type": "consumer"
                }
            )
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties
            )
            logger.info(f" [x] Sent message: {body}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise RabbitMQProducerException(f"Failed to send message: {e}")

    def close(self) -> None:
        """Close the connection to RabbitMQ."""
        if self.channel:
            self.channel.close()
            logger.info("Channel closed")
        if self.connection and self.connection.is_open:
            self.connection.close()
            logger.info("Connection closed")
        # Reset the singleton instance
        RabbitMQProducer._instance = None
        RabbitMQProducer._initialized = False
