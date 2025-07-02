#!/usr/bin/env python
import aio_pika
import logging
import asyncio
from app.client import RabbitMQClient

logger = logging.getLogger(__name__)

class RabbitMQProducerException(Exception):
    pass

class RabbitMQProducer:
    """Async RabbitMQ producer with connection pooling and non-blocking operations."""

    def __init__(self, client: RabbitMQClient):
        self.client = client
        self._connection: aio_pika.Connection | None = None
        self._channel: aio_pika.Channel | None = None
        self._lock = asyncio.Lock()

    async def ensure_connection(self) -> None:
        """Ensure connection is established."""
        if self._connection and not self._connection.is_closed:
            return
            
        async with self._lock:
            if self._connection and not self._connection.is_closed:
                return
                
            try:
                self._connection = await self.client.connect()
                self._channel = await self._connection.channel()   
                logger.info(f"Connected to RabbitMQ at {self.client.url}")             
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise RabbitMQProducerException(f"Failed to connect to RabbitMQ: {e}")

    async def send_message(self, exchange_name: str, client_id: str, ticket_id: str, routing_key: str, body: str) -> None:
        """Send a message asynchronously."""
        await self.ensure_connection()
        
        if not self._channel:
            raise RabbitMQProducerException("Channel not available")
        
        try:
        # Create message properties
            headers={
                "x-ticket-id": ticket_id,
                "x-client-id": client_id,
                "event_type": "request",
                "user_id": "some user_id",
                "group_id": "some group id",
                "target_type": "consumer"
            }

            # Create message
            message = aio_pika.Message(
                body=body.encode('utf-8'),
                headers=headers
            )
            if exchange_name:
                # Get or declare exchange
                exchange = await self._channel.get_exchange(exchange_name, ensure=True)
            else:
                # Use default exchange
                exchange = self._channel.default_exchange

            # Publish message
            await exchange.publish(message, routing_key=routing_key)
            
            logger.info(f" [x] Sent message: {body}")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise RabbitMQProducerException(f"Failed to send message: {e}")

    async def close(self) -> None:
        """Close the connection."""
        if self._channel:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
