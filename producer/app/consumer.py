import asyncio
import json
import logging
import functools
import pika

from datetime import datetime, timezone
from pika.channel import Channel
from pika.adapters.asyncio_connection import AsyncioConnection
from typing import Dict
from app.producer import RabbitMQProducer
from app.config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USERNAME, RABBITMQ_PASSWORD

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    """
    A class to manage the RabbitMQ connection and consumer.
    """
    def __init__(self, host: str = RABBITMQ_HOST, port: int = RABBITMQ_PORT, username: str = RABBITMQ_USERNAME, password: str = RABBITMQ_PASSWORD):
        self._connection: AsyncioConnection | None = None
        self._channel: Channel | None = None
        self._host = host
        self._port = port
        self._closing = False
        self.should_reconnect = False
        self.credentials = pika.PlainCredentials(username, password)
        self._consumer_tags = {} # queue_name -> consumer_tag
        self._reconnect_task = None

    def _connect(self):
        """Connect to RabbitMQ."""
        if self._connection and self._connection.is_open:
            logger.info("RabbitMQ connection already open.")
            return

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

        logger.info("RabbitMQ connection established.")


    def on_connection_open(self, connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :param pika.adapters.asyncio_connection.AsyncioConnection _unused_connection:
           The connection

        """
        logger.info('Connection opened')
        self._connection = connection
        self.open_channel(connection)

    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.

        :param pika.adapters.asyncio_connection.AsyncioConnection _unused_connection:
           The connection
        :param Exception err: The error

        """
        logger.error('Connection open failed: %s', err)
        self.reconnect()

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.

        """
        self._connection = None
        self.reconnect()


    def reconnect(self):
        self.should_reconnect = True
        self.stop()

    def open_channel(self, connection):
        """Open a new channel with RabbitMQ by issuing the Channel.Open RPC
        command. When RabbitMQ responds that the channel is open, the
        on_channel_open callback will be invoked by pika.

        """
        logger.info('Creating a new channel')
        connection.channel(on_open_callback=self.on_channel_open)


    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        logger.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.add_on_cancel_callback()


    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.

        """
        logger.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)


    def on_channel_closed(self, channel, reason):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel: The closed channel
        :param Exception reason: why the channel was closed

        """
        logger.warning('Channel %i was closed: %s', channel, reason)
        self._channel = None


    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.

        """
        logger.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)


    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        :param pika.frame.Method method_frame: The Basic.Cancel frame

        """
        logger.info('Consumer was cancelled remotely: %r', method_frame)

    def start_consuming(self, queue_name):
        """This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if RabbitMQ
        cancels the consumer. It then issues the Basic.Consume RPC command
        which returns the consumer tag that is used to uniquely identify the
        consumer with RabbitMQ. We keep the value to use it when we want to
        cancel consuming. The on_message method is passed in as a callback pika
        will invoke when a message is fully received.

        """
        logger.info('Issuing consumer related RPC commands')
        self._consumer_tags[queue_name] = self._channel.basic_consume(
            queue_name, self.on_message)


    def on_message(self, _unused_channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.

        :param pika.channel.Channel _unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param bytes body: The message body

        """
        try:
            ticket_id = properties.headers.get("x-ticket-id")
            # Decode the message body from bytes to string and parse JSON
            message = json.loads(body.decode('utf-8'))
            logger.info('Received message # %s from %s: %s',
                        basic_deliver.delivery_tag, properties.app_id, message)
            
            # Check if status is 'completed'
            if message.get('status') == 'completed':
                logger.info('Received completed status, stopping consumption')
                self.stop_consuming(basic_deliver.routing_key)
                logger.info(f"Sending event_logs message for ticket_id: {ticket_id}")
                message = json.dumps({
                    "ticket_id": ticket_id,
                    "user_id": "some user_id",
                    "group_id": "some group id",
                    "response_completion_time_in_ms": int(datetime.now(timezone.utc).timestamp() * 1000)
                })
                # Using default exchange to send a message directly to `database.request` queue
                with RabbitMQProducer() as rabbitmq_producer:
                    rabbitmq_producer.send_message(exchange="", ticket_id=ticket_id, routing_key="event_logs", message=message)
            else:
                logger.info('Acknowledging message %s', basic_deliver.delivery_tag)
                self._channel.basic_ack(basic_deliver.delivery_tag)
                
        except json.JSONDecodeError as e:
            logger.error('Failed to decode JSON message: %s', e)
            # Still acknowledge the message to prevent it from being requeued
            self._channel.basic_ack(basic_deliver.delivery_tag)
        except Exception as e:
            logger.error('Error processing message: %s', e)
            # Still acknowledge the message to prevent it from being requeued
            self._channel.basic_ack(basic_deliver.delivery_tag)


    def stop_consuming(self, queue_name):
        """Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.

        """
        if self._channel:
            logger.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            cb = functools.partial(
                self.on_cancelok, userdata=self._consumer_tags[queue_name])
            self._channel.basic_cancel(self._consumer_tags[queue_name], cb)


    def on_cancelok(self, _unused_frame, userdata):
        """This method is invoked by pika when RabbitMQ acknowledges the
        cancellation of a consumer.

        :param pika.frame.Method _unused_frame: The Basic.CancelOk frame
        :param str|unicode userdata: Extra user data (consumer tag)
        """
        logger.info(
            'RabbitMQ acknowledged the cancellation of the consumer: %s',
            userdata)

    def run(self):
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the AsyncioConnection to operate.

        """
        self._connection = self._connect()


    def stop(self):
        """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ.

        """
        self.close_connection()


    def close_connection(self):
        if self._connection and (self._connection.is_closing or self._connection.is_closed):
            logger.info('Connection is closing or already closed')
        elif self._connection:
            logger.info('Closing connection')
            self.close_channel()
            self._connection.close()
        else:
            logger.info('Connection is not open')

    def close_channel(self):
        """Call to close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.

        """
        if self._channel:
            logger.info('Closing the channel')
            self._channel.close()


class ReconnectingRabbitMQConsumer():
    def __init__(self, host: str = RABBITMQ_HOST, port: int = RABBITMQ_PORT, username: str = RABBITMQ_USERNAME, password: str = RABBITMQ_PASSWORD):
        self._host = host
        self._port = port
        self._reconnect_delay = 0
        self._consumer = RabbitMQConsumer(host, port, username, password)
        self.queue_names = []

    async def run(self):
        self._consumer.run()
        try:
            while True:
                await self._maybe_reconnect()
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            logger.info('Consumer task cancelled, cleaning up...')
            self._consumer.stop()
            raise
        except Exception as e:
            logger.error(f'Error in consumer loop: {e}')

    async def _maybe_reconnect(self):
        if self._consumer.should_reconnect:
            self._consumer.stop()
            reconnect_delay = self._get_reconnect_delay()
            logger.info('Reconnecting after %d seconds', reconnect_delay)
            await asyncio.sleep(reconnect_delay)
            self._consumer = RabbitMQConsumer(self._host, self._port)
            self._consumer.run()
            for queue_name in self.queue_names:
                self._consumer.start_consuming(queue_name)

    def start_consuming(self, queue_name):
        self.queue_names.append(queue_name)
        self._consumer.start_consuming(queue_name) 

    def stop_consuming(self, queue_name):
        self.queue_names.remove(queue_name)
        self._consumer.stop_consuming(queue_name)

    def _get_reconnect_delay(self):
        self._reconnect_delay += 1
        if self._reconnect_delay > 30:
            self._reconnect_delay = 30
        return self._reconnect_delay
