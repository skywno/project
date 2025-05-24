import asyncio
import json
import logging
import functools
import pika

from pika.adapters.asyncio_connection import AsyncioConnection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    """
    A class to manage the RabbitMQ connection and consumer.
    """
    def __init__(self, host: str = 'rabbitmq', port: int = 5672):
        self._connection: AsyncioConnection | None = None
        self._channel = None
        self._host = host
        self._port = port
        self._queues = {}  # queue_name -> consumer_tag
        self._consuming = False 
        self.credentials = pika.PlainCredentials('admin', 'admin')

    async def connect(self):
        """Connect to RabbitMQ."""
        if self._connection and self._connection.is_open:
            logger.info("RabbitMQ connection already open.")
            return
        while not self._connection:
            try:
                logger.info(f"Connecting to RabbitMQ at {self._host}:{self._port}")
                parameters = pika.ConnectionParameters(
                    host=self._host,
                    port=self._port,
                    credentials=self.credentials,
                    heartbeat=60 # Keep connection alive
                )
                self._connection = AsyncioConnection(
                        parameters=parameters,
                        on_open_callback=self.on_connection_open,
                        on_open_error_callback=self.on_connection_open_error,
                        on_close_callback=self.on_connection_closed,
                        custom_ioloop=asyncio.get_event_loop() # Ensure pika uses the FastAPI loop
                )
                await self._connection.connected.wait() # Wait for connection to establish
                logger.info("RabbitMQ connection established.")
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                logger.info(f"wait 10 secondss for the rabbitmq to run")
                await asyncio.sleep(10)

    def on_connection_open(self, connection: AsyncioConnection):
        """Called when the connection to RabbitMQ is established."""
        logger.info("Connection opened, creating channel...")
        connection.channel(on_open_callback=self.on_channel_open)

    def on_connection_open_error(self, connection: AsyncioConnection, err: Exception):
        """Called if the connection could not be established."""
        logger.error(f"Connection failed: {err}")
        connection.connected.set_exception(err)

    def on_connection_closed(self, connection: AsyncioConnection, reason: Exception):
        """Called when the connection to RabbitMQ is closed."""
        logger.warning(f"Connection closed: {reason}")
        self._channel = None
        self._queues.clear()  # Clear all queue tracking
        if self._consuming:
            logger.info("Attempting to reconnect in 5 seconds...")
            asyncio.get_event_loop().call_later(5, lambda: asyncio.create_task(self.connect()))

    def on_channel_open(self, channel):
        """Called when the channel is opened."""
        logger.info("Channel opened")
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)


    def on_channel_closed(self, channel, reason):
        """Called when the channel is closed."""
        logger.warning(f"Channel closed: {reason}")
        self._channel = None
        self._queues.clear()  # Clear all queue tracking
        # If the connection is still open, try to reopen the channel
        if self._connection and self._connection.is_open:
            self._connection.channel(on_open_callback=self.on_channel_open)

    async def add_queue(self, queue_name: str):
        """Add a new queue to consume from."""
        if not self._channel or not self._channel.is_open:
            await self.connect()
            if not self._channel:
                raise Exception("Failed to establish channel")

        if queue_name in self._queues:
            logger.info(f"Already consuming from queue: {queue_name}")
            return

        try:
            # We don't need to declare the queue here, because it is handled by the controller
            # Declare the queue
            # cb = functools.partial(self.on_queue_declared, userdata=queue_name)
            # self._channel.queue_declare(
            #     queue=queue_name,
            #     durable=True,
            #     callback=cb
            # )
            
            # We don't need to bind the queue to the exchange here, because it is handled by the controller
            # Bind the queue to the exchange
            # cb = functools.partial(self.on_queue_bound, userdata=queue_name)
            # self._channel.queue_bind(
            #     queue_name,
            #     self.EXCHANGE,
            #     routing_key=self.ROUTING_KEY,
            #     callback=cb
            # )

            # Start consuming from the queue
            consumer_tag = self._channel.basic_consume(
                queue=queue_name,
                on_message_callback=self.on_message_callback,
                auto_ack=False
            )
            
            self._queues[queue_name] = consumer_tag
            logger.info(f"Started consuming from queue: {queue_name}")
        except Exception as e:
            logger.error(f"Failed to add queue {queue_name}: {e}")
            raise

    # def on_queue_declared(self, frame, userdata):
    #     """Called when the queue is successfully declared.
    #     userdata is the queue name.
    #     """
    #     logger.info(f"Queue '{userdata}' declared.")
    
    # def on_queue_bound(self, frame, userdata):
    #     """Invoked by pika when the Queue.Bind method has completed. At this
    #     point we will set the prefetch count for the channel.

    #     :param pika.frame.Method _unused_frame: The Queue.BindOk response frame
    #     :param str|unicode userdata: Extra user data (queue name)

    #     """
    #     logger.info(f'Queue bound: {userdata}')

    def on_message_callback(self, channel, method, properties, body):
        """
        Callback function for processing incoming messages.
        This function is called for each message received.
        """
        queue_name = method.routing_key
        logger.info(f"Received message from queue {queue_name}: {body.decode()}")
        try:
            message_data = json.loads(body.decode())
            # Process the message here.
            # For demonstration, let's just print it.
            logger.info(f"Processed data from queue {queue_name}: {message_data}")

            # Acknowledge the message to RabbitMQ
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON message from queue {queue_name}: {body.decode()}")
            # Nack the message if it's malformed, don't re-queue for now
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message from queue {queue_name}: {e}", exc_info=True)
            # Nack the message, potentially re-queue based on error handling
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    async def remove_queue(self, queue_name: str):
        """Stop consuming from a specific queue."""
        if queue_name not in self._queues:
            logger.warning(f"Not consuming from queue: {queue_name}")
            return

        if self._channel and self._channel.is_open:
            try:
                await asyncio.to_thread(
                    self._channel.basic_cancel,
                    self._queues[queue_name]
                )
                del self._queues[queue_name]
                logger.info(f"Stopped consuming from queue: {queue_name}")
            except Exception as e:
                logger.error(f"Failed to remove queue {queue_name}: {e}")
                raise
    async def start_consuming(self):
        """Start the Pika I/O loop to consume messages."""
        if not self._connection or not self._connection.is_open:
            await self.connect()

        # The Pika AsyncioConnection integrates with the asyncio event loop.
        # Once connected, the callbacks will be triggered.
        # We don't need to call _connection.ioloop.start() explicitly
        # because FastAPI is already running the asyncio event loop.
        self._consuming = True

        logger.info("RabbitMQ consumer is running in background.")
        # Keep the consumer active indefinitely by just letting it run
        # within the FastAPI event loop.
        while self._consuming and self._connection and self._connection.is_open:
            await asyncio.sleep(1) # Keep the task alive, allow other tasks to run

    async def stop_consuming(self):
        """Stop consuming messages and close the connection."""
        self._consuming = False
        
        # Cancel all consumers
        if self._channel and self._channel.is_open:
            for queue_name, consumer_tag in list(self._queues.items()):
                try:
                    await asyncio.to_thread(self._channel.basic_cancel, consumer_tag)
                    logger.info(f"Cancelled consumer for queue: {queue_name}")
                except Exception as e:
                    logger.error(f"Error cancelling consumer for queue {queue_name}: {e}")
            
            self._queues.clear()
            logger.info("Closing channel...")
            await asyncio.to_thread(self._channel.close)
            self._channel = None

        if self._connection and self._connection.is_open:
            logger.info("Closing connection...")
            await asyncio.to_thread(self._connection.close)
            self._connection = None
        logger.info("RabbitMQ consumer stopped.")


    def on_connection_closed(self, connection: AsyncioConnection, reason: Exception):
        """Called when the connection to RabbitMQ is closed."""
        logger.warning(f"Connection closed: {reason}")
        self._channel = None
        self._queues.clear()  # Clear all queue tracking
        if self._consuming:
            logger.info("Attempting to reconnect in 5 seconds...")
            asyncio.get_event_loop().call_later(5, lambda: asyncio.create_task(self.connect()))
