#!/usr/bin/env python
import pika
import time
import sys
import os
import logging 

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def main():
    consumer_id = str(os.environ.get('CONSUMER_ID'))
    logging.info(f" [*] Consumer {consumer_id} started")

    credentials = pika.PlainCredentials('admin', 'admin')
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials=credentials))
    channel = connection.channel()

    channel.exchange_declare(exchange='consumer_exchange', exchange_type='topic')

    result = channel.queue_declare(queue='consumer_queue')
    queue_name = result.method.queue

    channel.queue_bind(exchange='consumer_exchange',
                        queue=queue_name,
                        routing_key='service.consumer.request')

    channel.basic_consume(queue=queue_name,
                        auto_ack=False,
                        on_message_callback=callback)

    logging.info(' [*] Waiting for messages. To exit press CTRL+C')

    channel.basic_qos(prefetch_count=1)
    channel.start_consuming()

def callback(ch, method, properties, body):
    logging.info(f" [x] Received {body.decode()}")
    time.sleep(3)
    logging.info(" [x] Done")
    ch.basic_ack(delivery_tag=method.delivery_tag)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)