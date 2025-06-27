import pika
import json
from app.db import save_request, save_response, save_queue_deleted, save_data
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


#deprecated
def request_callback(ch, method, properties, body):
    logger.info("Received message from request queue: %s", body.decode())
    try:
        headers = properties.headers
        data = json.loads(body.decode('utf-8'))
        save_request(headers, data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")

#deprecated
def response_callback(ch, method, properties, body):
    try:
        headers = properties.headers
        data = json.loads(body.decode('utf-8'))
        save_response(headers, data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")

#deprecated
def queue_deleted_callback(ch, method, properties, body):
    try:
        headers = properties.headers
        logger.info(f"Queue deleted headers: {headers}")
        save_queue_deleted(headers)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def on_message_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode('utf-8'))
        save_data(properties.headers, data)    
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

    queue = "event_logs"

    channel.queue_declare(queue, durable=True)
    channel.basic_consume(queue=queue, on_message_callback=on_message_callback, auto_ack=False)
    logger.info("Waiting for messages...")
    channel.start_consuming()