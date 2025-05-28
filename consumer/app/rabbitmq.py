import asyncio
import aio_pika
import logging
from app.client import get_exchange_and_routing_key

logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self, url: str = "amqp://admin:admin@rabbitmq:5672/"):
        self.url = url
        self.connection = None
    
    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.url)

    async def close(self):
        await self.connection.close()

class RabbitMQConsumer():
    def __init__(self, client: RabbitMQClient,):
        self.client = client
        self.queue = None
        self.channel = None
        self._task = None

    async def connect(self, queue_name: str):
        try:
            self.queue_name = queue_name
            self.channel = await self.client.connection.channel()
            self.queue = await self.channel.get_queue(self.queue_name, ensure = True)
        except aio_pika.exceptions.ChannelClosed as e:
            logger.error(f"Channel closed: {e}")
        except Exception as e:
            logger.error(f"Error connecting to queue {self.queue_name}: {e}")
            raise e
        
    async def start(self):
        self._task = asyncio.create_task(self._consume())
    
    async def _consume(self):
        await self.queue.consume(self._on_message)


    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        ticket_id = message.headers.get("x-ticket-id")
        exchange, routing_key = await get_exchange_and_routing_key(ticket_id)
        rabbitmq_publisher = RabbitMQPublisher(self.client, exchange)
        await rabbitmq_publisher.connect()
        async with message.process() as processed_message:
            for status in range(0, 100, 10):
                await rabbitmq_publisher.publish(f"ticket {ticket_id} is {status}% complete", routing_key, ticket_id)
                await asyncio.sleep(1)
            await rabbitmq_publisher.publish(f"ticketc {ticket_id} is 100% complete", routing_key, ticket_id)
        await rabbitmq_publisher.close()
    
    async def close(self):
        self.channel.close()

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Consumer stopped.")
            finally:
                await self.close()
            

class RabbitMQPublisher():
    def __init__(self, client: RabbitMQClient, exchange_name: str):
        self.client = client
        self.exchange_name = exchange_name
        self.channel = None
        self.exchange = None

    async def connect(self):
        try:
            self.channel = await self.client.connection.channel()
            self.exchange = await self.channel.get_exchange(self.exchange_name, ensure = True)
        except aio_pika.exceptions.ChannelClosed as e:
            logger.error(f"Channel closed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Error connecting to exchange {self.exchange_name}: {e}")
            raise e
    
    async def publish(self, message: str, routing_key: str, ticket_id: str):
        try:
            await self.exchange.publish(
                message = aio_pika.Message(
                    body = message.encode(),
                    headers = {
                        "x-ticket-id": ticket_id
                    }
                ),
                routing_key = routing_key
            )
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            raise e
        
    async def close(self):
        await self.channel.close()
