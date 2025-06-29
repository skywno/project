import asyncio
import aio_pika
import logging
import json
import uuid

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.client import get_exchange_and_routing_key
from app.config import RABBITMQ_URL, TIME_TO_FIRST_TOKEN, INTER_TOKEN_LATENCY, OUTPUT_LENGTH, REQUEST_LATENCY, ENABLE_STREAMING, MAX_CONCURRENT_REQUESTS
from lorem_text import lorem

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
        self.active_requests = 0
        
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
        message.headers.update({"event_type": "response"})

        if not ticket_id:
            logger.error("Message received without ticket_id")
            await message.nack(requeue=False)
            return

        try:
            self.active_requests += 1
            exchange, routing_key = await get_exchange_and_routing_key(ticket_id)

            # Acquire semaphore before creating publisher connection
            async with InferenceSimulator.concurrency_semaphore:
                logger.info(f"[{ticket_id}] Request started. Active requests: {self.active_requests}/{MAX_CONCURRENT_REQUESTS}")
                async with RabbitMQPublisher(self.client, exchange) as publisher:
                    async with message.process():
                        await self._process_ticket(publisher, ticket_id, routing_key, message.headers)
                logger.info(f"Published message for ticket {ticket_id} to exchange {exchange} with routing key {routing_key}")
                    
        except Exception as e:
            logger.error(f"Error duringprocessing message for ticket {ticket_id}: {e}")
            await message.nack(requeue=True)
            raise
        finally:
            self.active_requests -= 1
            logger.info(f"[{ticket_id}] Request completed. Active requests: {self.active_requests}/{MAX_CONCURRENT_REQUESTS}")

    async def _process_ticket(self, publisher: 'RabbitMQPublisher', ticket_id: str, routing_key: str, headers: dict) -> None:
        """Process ticket status updates."""
        job_id = str(uuid.uuid4())
        if ENABLE_STREAMING:
            await publisher.publish_stream(job_id, ticket_id, routing_key, headers)
        else:
            await publisher.publish_batch(job_id, ticket_id, routing_key, headers)

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


    async def publish_stream(self, job_id: str, ticket_id: str, routing_key: str, headers: dict):
        """Publish a stream of tokens to the exchange."""
        try:
            start_time = datetime.now(timezone.utc)
            async for token, is_first, is_last in InferenceSimulator.mock_inference_stream():
                if is_first:
                    # Publish first token with different message structure
                    await self._publish_started(token, routing_key, start_time, job_id, headers)
                elif is_last:
                    # Publish last token with different message structure
                    await self._publish_completed(token, routing_key, start_time, job_id, headers)
                else:
                    # Publish subsequent tokens
                    await self._publish_in_progress(token, routing_key, start_time, job_id, headers)
        except Exception as e:
            logger.error(f"Error publishing stream for ticket {ticket_id}: {e}")
            raise

    async def _publish_started(self, token: str, routing_key: str, start_time: datetime, job_id: str, headers: dict):
        """Publish the first token with special message structure."""
        body = {
            "tokens": token,
            "status": "started",
            "ticket_id": headers.get("x-ticket-id"),
            "job_id": job_id,
            "service_processing_start_time": start_time.isoformat(),
            "service_processing_last_update_time": datetime.now(timezone.utc).isoformat(),
        }
        await self._publish(body, routing_key, headers)

    async def _publish_in_progress(self, message: str, routing_key: str, start_time: datetime, job_id: str, headers: dict):
        body = {
            "tokens": message,
            "status": "in_progress",
            "ticket_id": headers.get("x-ticket-id"),
            "service_processing_start_time": start_time.isoformat(),
            "service_processing_last_update_time": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
        }
        await self._publish(body, routing_key, headers)
    
    async def _publish_completed(self, message: str, routing_key: str, start_time: datetime, job_id: str, headers: dict):
        body = {
            "tokens": message,
            "status": "completed",
            "ticket_id": headers.get("x-ticket-id"),
            "service_processing_start_time": start_time.isoformat(),
            "service_processing_end_time": datetime.now(timezone.utc).isoformat(),
            "service_processing_last_update_time": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
        }
        await self._publish(body, routing_key, headers)

    async def publish_batch(self, job_id: str, ticket_id: str, routing_key: str, headers: dict):
        """Publish a batch of tokens to the exchange."""
        try:
            start_time = datetime.now(timezone.utc)
            await asyncio.sleep(REQUEST_LATENCY * 0.001) # convert to seconds
            end_time = datetime.now(timezone.utc)
            body = {
                "tokens": lorem.words(OUTPUT_LENGTH),
                "status": "completed",
                "ticket_id": ticket_id,
                "service_processing_start_time": start_time.isoformat(),
                "service_processing_end_time": end_time.isoformat(),
                "service_processing_last_update_time": end_time.isoformat(),
                "job_id": job_id,
            }
            await self._publish(body, routing_key, headers)
        except Exception as e:
            logger.error(f"Error publishing batch for ticket {ticket_id}: {e}")
            raise

    async def _publish(self, body: dict, routing_key: str, headers: dict) -> None:
        """Publish a message to the exchange."""
        if not self.exchange:
            raise RuntimeError("Publisher not connected to exchange")
        try:
            ticket_id = headers.get("x-ticket-id")
            message_body = json.dumps(body)
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
        
class InferenceSimulator:
    # Class variables - shared across all instances
    concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    time_to_first_token = TIME_TO_FIRST_TOKEN
    inter_token_latency = INTER_TOKEN_LATENCY
    output_length = OUTPUT_LENGTH

    @classmethod
    async def mock_inference_stream(cls):
        """
        Simulates a streaming inference response that yields tokens.
        - Simulates time to first token (TTFT)
        - Simulates latency between tokens
        """
        # Simulate delay before first token (Time to First Token)
        # await asyncio.sleep(cls.time_to_first_token * 0.001) # convert to seconds
        await asyncio.sleep(10)
        for i in range(cls.output_length):
            is_first = i == 0
            is_last = i == cls.output_length - 1
            yield f"token_{i}", is_first, is_last  # Return token, is_first, and is_last
            await asyncio.sleep(cls.inter_token_latency * 0.001) # convert to seconds
