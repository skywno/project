import pika
import json
from app.db import save_record

def callback(ch, method, properties, body):
    print("Received message:", body)
    try:
        data = json.loads(body)
        save_record(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error processing message: {e}")

def start_consumer():
    credentials = pika.PlainCredentials('admin', 'admin')
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials=credentials))
    channel = connection.channel()

    QUEUE_NAME = "database_helper_queue"

    channel.exchange_declare('producer_exchange', exchange_type='fanout')
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.queue_bind("database_helper_queue", "producer_exchange", routing_key="")

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)

    print("Waiting for messages...")
    channel.start_consuming()