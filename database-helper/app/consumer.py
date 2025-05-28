import pika
import json
from app.db import save_record
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def request_callback(ch, method, properties, body):
    logger.info("Received message from request queue: %s", body.decode())
    try:
        data = json.loads(body.decode('utf-8'))
        save_record(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def response_callback(ch, method, properties, body):
    try:
        message = body.decode('utf-8')
        logger.info("Received message from response queue: %s", message)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")


def start_consumer():
    RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD")
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
    RABBITMQ_PORT = os.getenv("RABBITMQ_PORT")

    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials))
    channel = connection.channel()

    request_queue = "database.request"
    response_queue = "database.response"
    channel.queue_declare(request_queue)
    channel.queue_declare(response_queue)
    channel.basic_consume(queue=request_queue, on_message_callback=request_callback, auto_ack=False)
    channel.basic_consume(queue=response_queue, on_message_callback=response_callback, auto_ack=False)
    logger.info("Waiting for messages...")
    channel.start_consuming()