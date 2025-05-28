#!/usr/bin/env python
import pika
from typing import Optional
import logging
from pika.spec import BasicProperties
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RabbitMQProducer:
    def __init__(self, host: str = 'rabbitmq', username: str = 'admin', password: str = 'admin'):
        self.host = host
        self.connection = None
        self.channel = None
        self.credentials = pika.PlainCredentials(username, password)

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
            raise

    def send_message(self, exchange: str, ticket_id: str, routing_key: str, message: str) -> None:
        """Send a message to the specified queue."""
        if not self.connection or not self.channel:
            self.connect()
        
        try:
            properties = BasicProperties(
                headers={
                    "x-ticket-id": ticket_id
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
            raise

    def close(self) -> None:
        """Close the connection to RabbitMQ."""
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