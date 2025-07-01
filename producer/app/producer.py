#!/usr/bin/env python
import pika
import logging

from pika.spec import BasicProperties
from app.config import RABBITMQ_HOST, RABBITMQ_USERNAME, RABBITMQ_PASSWORD

logger = logging.getLogger(__name__)

class RabbitMQProducerException(Exception):
    pass

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
