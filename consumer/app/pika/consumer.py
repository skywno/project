import asyncio
import json
import logging
import pika
from pika.channel import Channel
from typing import Callable
from pika.adapters.asyncio_connection import AsyncioConnection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    """
    A class to manage the RabbitMQ connection and consumer.
    """
    def __init__(self, host: str, port: int, queue_name: str, on_message_callback: Callable):
        self._connection: AsyncioConnection | None = None
        self._channel = None
        self._host = host
        self._port = port
        self._queue_name = queue_name
        self._consuming = False
        self._consumer_tag = None
        self.on_message_callback = on_message_callback

    def connect(self):
        """Connect to RabbitMQ."""
        if self._connection and self._connection.is_open:
            logger.info("RabbitMQ connection already open.")
            return

        try:
            logger.info(f"Connecting to RabbitMQ at {self._host}:{self._port}")
            parameters = pika.ConnectionParameters(
                host=self._host,
                port=self._port,
                heartbeat=60 # Keep connection alive
            )
            self._connection = AsyncioConnection(
                parameters=parameters,
                on_open_callback=self.on_connection_open,
                on_open_error_callback=self.on_connection_open_error,
                on_close_callback=self.on_connection_closed,
                custom_ioloop=asyncio.get_event_loop() # Ensure pika uses the FastAPI loop
            )
            logger.info("RabbitMQ connection established.")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

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
        self._channel = None # Reset channel as connection is closed
        if self._consuming:
            logger.info("Attempting to reconnect in 5 seconds...")
            asyncio.get_event_loop().call_later(5, lambda: asyncio.create_task(self.connect()))


    def on_channel_open(self, channel):
        """Called when the channel is opened."""
        logger.info("Channel opened, declaring queue...")
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)
        self._channel.queue_declare(
            queue=self._queue_name, durable=True, callback=self.on_queue_declared
        )

    def on_channel_closed(self, channel, reason):
        """Called when the channel is closed."""
        logger.warning(f"Channel closed: {reason}")
        self._channel = None
        # If the connection is still open, try to reopen the channel
        if self._connection and self._connection.is_open:
            self._connection.channel(on_open_callback=self.on_channel_open)


    def on_queue_declared(self, frame):
        """Called when the queue is successfully declared."""
        logger.info(f"Queue '{self._queue_name}' declared.")
        self._consuming = True
        self._consumer_tag = self._channel.basic_consume(
            queue=self._queue_name, on_message_callback=self.on_message_callback
        )
        logger.info("Starting consuming messages...")


    def start_consuming(self):
        """Start the Pika I/O loop to consume messages."""
        if not self._connection or not self._connection.is_open:
            self.connect()

        # The Pika AsyncioConnection integrates with the asyncio event loop.
        # Once connected, the callbacks will be triggered.
        # We don't need to call _connection.ioloop.start() explicitly
        # because FastAPI is already running the asyncio event loop.
        logger.info("RabbitMQ consumer is running in background.")

    def stop_consuming(self):
        """Stop consuming messages and close the connection."""
        if self._consuming and self._channel:
            logger.info("Cancelling consumer...")
            self._channel.basic_cancel(self._consumer_tag)
            self._consuming = False

        if self._channel and self._channel.is_open:
            logger.info("Closing channel...")
            self._channel.close()
            self._channel = None

        if self._connection and self._connection.is_open:
            logger.info("Closing connection...")
            self._connection.close()
            self._connection = None
        logger.info("RabbitMQ consumer stopped.")
