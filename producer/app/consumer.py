import asyncio
import json
import logging
import aio_pika
from datetime import datetime, timezone
from typing import Dict, Optional
from app.producer import RabbitMQProducer
from app.client import RabbitMQClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    """
    A class to manage the RabbitMQ connection and consumer using aio-pika.
    """
    def __init__(self, client: RabbitMQClient):
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._client = client
        self._closing = False
        self._consumer_tags = {}  # queue_name -> consumer_tag
        self._producer = RabbitMQProducer(client)

    async def _connect(self):
        """Connect to RabbitMQ."""
        if self._connection and not self._connection.is_closed:
            logger.info("RabbitMQ connection already open.")
            return
        try:
            self._connection = await self._client.connect()
            self._channel = await self._connection.channel()
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def start_consuming(self, queue_name: str):
        """Start consuming messages from the specified queue."""
        await self._connect()
        
        if not self._channel:
            raise Exception("Channel not available")
        
        try:
            # Get queue
            queue = await self._channel.get_queue(queue_name)
            
            # Create consumer
            consumer_tag = await queue.consume(self._on_message)
            self._consumer_tags[queue_name] = consumer_tag
            
            logger.info(f'Started consuming from queue: {queue_name}')
            
        except Exception as e:
            logger.error(f"Failed to start consuming from queue {queue_name}: {e}")
            raise
    
    async def stop_consuming(self, queue_name: str):
        if queue_name in self._consumer_tags:
            queue = await self._channel.get_queue(queue_name)
            await queue.cancel(self._consumer_tags[queue_name])
            del self._consumer_tags[queue_name]
            logger.info(f'Stopped consuming from queue: {queue_name}')
        else:
            logger.warning(f'Queue {queue_name} not found')

    async def _on_message(self, message: aio_pika.IncomingMessage):
        """Process incoming messages."""
        async with message.process():
            try:
                ticket_id = message.headers.get("x-ticket-id") if message.headers else None
                
                # Decode the message body from bytes to string and parse JSON
                body = message.body.decode('utf-8')
                message_data = json.loads(body)
                
                if message_data.get('status') == 'started':
                    logger.info('Received started status, starting consumption')
                    body = json.dumps({
                        "time_to_first_token": datetime.now(timezone.utc).isoformat()
                    })
                    # Using default exchange to send a message directly to `event_logs` queue
                    await self._producer.send_message(exchange_name="", client_id=None, ticket_id=ticket_id, routing_key="event_logs", body=body)
                    
                # Check if status is 'completed'
                elif message_data.get('status') == 'completed':
                    logger.info('Received completed status')
                    logger.info(f"Sending event_logs message for ticket_id: {ticket_id}")
                    body = json.dumps({
                        "request_completion_time": datetime.now(timezone.utc).isoformat()
                    })
                    # Using default exchange to send a message directly to `event_logs` queue
                    await self._producer.send_message(exchange_name="", client_id=None, ticket_id=ticket_id, routing_key="event_logs", body=body)
                    await self.stop_consuming(message.routing_key)
            except json.JSONDecodeError as e:
                logger.error('Failed to decode JSON message: %s', e)
            except Exception as e:
                logger.error('Error processing message: %s', e)


    async def run(self):
        """Run the consumer."""
        await self._connect()

    async def stop(self):
        """Cleanly shutdown the connection to RabbitMQ."""
        await self.close_connection()
        await self._producer.close()

    async def close_connection(self):
        """Close the connection to RabbitMQ."""
        if self._connection and not self._connection.is_closed:
            logger.info('Closing connection')
            await self.close_channel()
            await self._connection.close()
        else:
            logger.info('Connection is not open')

    async def close_channel(self):
        """Close the channel with RabbitMQ."""
        if self._channel:
            logger.info('Closing the channel')
            await self._channel.close()
