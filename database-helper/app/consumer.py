import pika
import json
from app.db import save_request, save_response, save_queue_deleted
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def request_callback(ch, method, properties, body):
    logger.info("Received message from request queue: %s", body.decode())
    try:
        headers = properties.headers
        data = json.loads(body.decode('utf-8'))
        save_request(headers, data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def response_callback(ch, method, properties, body):
    try:
        headers = properties.headers
        data = json.loads(body.decode('utf-8'))
        save_response(headers, data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def queue_deleted_callback(ch, method, properties, body):
    try:
        headers = properties.headers
        logger.info(f"Queue deleted headers: {headers}")
        save_queue_deleted(headers)
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
    queue_deleted_queue = "queue_created"
    event_exchange_name = "amq.rabbitmq.event"
    routing_key = "queue.deleted"

    channel.queue_declare(request_queue, durable=True)
    channel.queue_declare(response_queue, durable=True)
    channel.queue_declare(queue_deleted_queue, durable=True)
    channel.queue_bind(queue=queue_deleted_queue, exchange=event_exchange_name, routing_key=routing_key)
    channel.basic_consume(queue=request_queue, on_message_callback=request_callback, auto_ack=False)
    channel.basic_consume(queue=response_queue, on_message_callback=response_callback, auto_ack=False)
    channel.basic_consume(queue=queue_deleted_queue, on_message_callback=queue_deleted_callback, auto_ack=False)
    logger.info("Waiting for messages...")
    channel.start_consuming()