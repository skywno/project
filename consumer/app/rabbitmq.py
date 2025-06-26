import asyncio
import aio_pika
import logging
import json
from datetime import datetime, timezone

from typing import Optional, Dict, Any
from app.client import get_exchange_and_routing_key
from app.config import RABBITMQ_URL

logger = logging.getLogger(__name__)

class RabbitMQConnectionError(Exception):
    """Custom exception for RabbitMQ connection errors."""
    pass

class RabbitMQClient:
    def __init__(self, url: str = RABBITMQ_URL, max_retries: int = 10, retry_delay: int = 10):
        self.url = url
        self.connection: Optional[aio_pika.Connection] = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def connect(self) -> None:
        """Establish connection to RabbitMQ with retry logic."""
        retries = 0
        while retries < self.max_retries:
            try:
                self.connection = await aio_pika.connect_robust(self.url)
                logger.info("Successfully connected to RabbitMQ")
                return
            except Exception as e:
                retries += 1
                logger.error(f"Error connecting to RabbitMQ (attempt {retries}/{self.max_retries}): {e}")
                if retries < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds")
                    await asyncio.sleep(self.retry_delay)
        
        raise RabbitMQConnectionError(f"Failed to connect to RabbitMQ after {self.max_retries} attempts")

    async def close(self) -> None:
        """Close the RabbitMQ connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("RabbitMQ connection closed")

class RabbitMQConsumer:
    def __init__(self, client: RabbitMQClient):
        self.client = client
        self.queue: Optional[aio_pika.Queue] = None
        self.channel: Optional[aio_pika.Channel] = None
        self._task: Optional[asyncio.Task] = None
        self._is_consuming: bool = False

    async def connect(self, queue_name: str) -> None:
        """Connect to a specific queue."""
        try:
            self.queue_name = queue_name
            self.channel = await self.client.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            self.queue = await self.channel.get_queue(self.queue_name, ensure=True)
            logger.info(f"Successfully connected to queue: {queue_name}")
        except aio_pika.exceptions.ChannelClosed as e:
            logger.error(f"Channel closed: {e}")
            self.channel = None
            self.queue = None
            raise
        except Exception as e:
            logger.error(f"Error connecting to queue {queue_name}: {e}")
            self.channel = None
            self.queue = None
            raise

    async def start(self) -> None:
        """Start consuming messages."""
        if not self._is_consuming and self.channel and self.queue:
            self._is_consuming = True
            self._task = asyncio.create_task(self._consume())
            logger.info("Started consuming messages")
        else:
            logger.info("Already consuming messages")

    async def _consume(self) -> None:
        """Internal method to consume messages."""
        try:
            await self.queue.consume(self._on_message)
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            self._is_consuming = False
            raise

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Process incoming messages."""
        ticket_id = message.headers.get("x-ticket-id")
        if not ticket_id:
            logger.error("Message received without ticket_id")
            await message.nack(requeue=False)
            return

        try:
            exchange, routing_key = await get_exchange_and_routing_key(ticket_id)
            if not exchange or not routing_key:
                logger.error(f"Failed to get exchange info for ticket {ticket_id}")
                await message.nack(requeue=True)
                return

            async with RabbitMQPublisher(self.client, exchange) as publisher:
                async with message.process():
                    await self._process_ticket_status(publisher, ticket_id, routing_key)
            logger.info(f"Published message for ticket {ticket_id} to exchange {exchange} with routing key {routing_key}")
        except Exception as e:
            logger.error(f"Error duringprocessing message for ticket {ticket_id}: {e}")
            await message.nack(requeue=True)
            raise

    async def _process_ticket_status(self, publisher: 'RabbitMQPublisher', ticket_id: str, routing_key: str) -> None:
        """Process ticket status updates."""
        try:
            service_processing_start_time = datetime.now(timezone.utc)
            for status in range(0, 100, 20):
                await publisher.publish_in_progress(
                    f"ticket {ticket_id} is {status}% complete",
                    routing_key,
                    ticket_id,
                    service_processing_start_time
                )
                await asyncio.sleep(1)
            await publisher.publish_completed(
                f"ticket {ticket_id} is 100% complete",
                routing_key,
                ticket_id,
                service_processing_start_time
            )
        except Exception as e:
            logger.error(f"Error processing ticket status for {ticket_id}: {e}")
            raise

    async def close(self) -> None:
        """Close the consumer channel."""
        if self.channel:
            await self.channel.close()
            self.channel = None
            logger.info("Consumer channel closed")

    async def stop(self) -> None:
        """Stop consuming messages and clean up resources."""
        if self._task:
            self._is_consuming = False
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Consumer stopped")
            finally:
                await self.close()

class RabbitMQPublisher:
    def __init__(self, client: RabbitMQClient, exchange_name: str):
        self.client = client
        self.exchange_name = exchange_name
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def __aenter__(self) -> 'RabbitMQPublisher':
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Connect to the exchange."""
        try:
            self.channel = await self.client.connection.channel()
            self.exchange = await self.channel.get_exchange(self.exchange_name, ensure=True)
            logger.info(f"Successfully connected to exchange: {self.exchange_name}")
        except aio_pika.exceptions.ChannelClosed as e:
            logger.error(f"Channel closed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error connecting to exchange {self.exchange_name}: {e}")
            raise
    
    async def close(self) -> None:
        """Close the publisher channel."""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.exchange = None
            logger.info("Publisher channel closed")

    async def publish_in_progress(self, message: str, routing_key: str, ticket_id: str, start_time: datetime):
        headers = {
            "x-ticket-id": ticket_id,
            "service_processing_start_time_in_ms": int(start_time.timestamp() * 1000),
            "service_processing_last_update_time_in_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        await self.publish(message, "in_progress", routing_key, ticket_id, headers)
    
    async def publish_completed(self, message: str, routing_key: str, ticket_id: str, start_time: datetime):
        headers = {
            "x-ticket-id": ticket_id,
            "service_processing_start_time_in_ms": int(start_time.timestamp() * 1000),
            "service_processing_end_time_in_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "service_processing_last_update_time_in_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        await self.publish(message, "completed", routing_key, ticket_id, headers)
    

    async def publish(self, message: str, status: str, routing_key: str, ticket_id: str, headers: dict) -> None:
        """Publish a message to the exchange."""
        if not self.exchange:
            raise RuntimeError("Publisher not connected to exchange")
        try:
            message_body = json.dumps({
                "message": message,
                "status": status,
                "ticket_id": ticket_id
            })
            await self.exchange.publish(
                message=aio_pika.Message(
                    body=message_body.encode(),
                    headers=headers
                ),
                routing_key=routing_key
            )
            logger.debug(f"Published message for ticket {ticket_id}")
        except Exception as e:
            logger.error(f"Error publishing message for ticket {ticket_id}: {e}")
            raise
        
