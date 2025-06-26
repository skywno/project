#!/usr/bin/env python
import pika
import logging
import datetime

from pika.spec import BasicProperties
from app.config import RABBITMQ_HOST, RABBITMQ_USERNAME, RABBITMQ_PASSWORD

logger = logging.getLogger(__name__)

class RabbitMQProducerException(Exception):
    pass

class RabbitMQProducer:
    def __init__(self, host: str = RABBITMQ_HOST, username: str = RABBITMQ_USERNAME, password: str = RABBITMQ_PASSWORD):
        self.host = host
        self.connection : pika.BlockingConnection | None = None
        self.channel : pika.BlockingChannel | None = None
        self.credentials = pika.PlainCredentials(username, password)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def connect(self) -> None:
        """Establish connection to RabbitMQ server."""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, credentials=self.credentials)
            )
            self.channel = self.connection.channel()
            logger.info(f"Connected to RabbitMQ at {self.host}")
            
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise RabbitMQProducerException(f"Failed to connect to RabbitMQ: {e}")

    def send_message(self, exchange: str, ticket_id: str, routing_key: str, message: str) -> None:
        """Send a message to the specified queue."""
        if not self.connection or not self.channel:
            self.connect()
        
        try:
            properties = BasicProperties(
                headers={
                    "x-ticket-id": ticket_id,
                    "client_request_send_time_in_ms": int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
                }
            )
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=message,
                properties=properties
            )
            logger.info(f" [x] Sent message: {message}")
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

def main():
    producer = RabbitMQProducer()
    try:
        producer.send_message("Hello World!")
    finally:
        producer.close()

if __name__ == "__main__":
    main()