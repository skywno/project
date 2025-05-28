import httpx
import sys
import logging
from typing import Dict, Tuple
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
http_client = httpx.AsyncClient()

CONTROLLER_SERVICE_URL = os.getenv("CONTROLLER_SERVICE_URL") or "http://controller:8000"
CONSUMER_SERVICE_URL = os.getenv("CONSUMER_SERVICE_URL") or "http://consumer-1:8000"
SERVICE_TYPE = "consumer"

async def check_service_health():
    try:
        response = await http_client.get(f"{CONTROLLER_SERVICE_URL}/health")
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"Error checking service health: {e}")
        return False

async def send_register_request_and_get_queue() -> str | None:
    body = {
        "service_name": "consumer",
        "service_type": SERVICE_TYPE,
        "service_url": CONSUMER_SERVICE_URL,
        "service_description": "Consumer service"
    }
    try:
        response = await http_client.post(f"{CONTROLLER_SERVICE_URL}/service/register", json=body)
        logging.info(f"Registered service: {response.json()}")
        return response.json()["queue_name"]

    except Exception as e:
        logging.error(f"Error registering service: {e}")
        return None


# async def subscribe_to_queue(queue: str):
#     try:
#         consumer = RabbitMQConsumer("rabbitmq", 5672, queue, on_message_callback)
#         await consumer.start_consuming()
#     except Exception as e:
#         logging.error(f"Error subscribing to queue: {e}")
#         return None


# def on_message_callback(channel, method, properties, body):
#     """
#     Callback function for processing incoming messages.
#     This function is called for each message received.
#     """
#     logging.info(f"Received message: {body.decode()}")
#     try:
#         message_data = json.loads(body.decode())
#         # Process the message here.
#         # For demonstration, let's just print it.
#         logging.info(f"Processed data: {message_data}")
#         asyncio.create_task(handle_task(message_data))
#         # Acknowledge the message to RabbitMQ
#         channel.basic_ack(delivery_tag=method.delivery_tag)
#     except json.JSONDecodeError:
#         logging.error(f"Failed to decode JSON message: {body.decode()}")
#         # Nack the message if it's malformed, don't re-queue for now
#         channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
#     except Exception as e:
#         logging.error(f"Error processing message: {e}", exc_info=True)
#         # Nack the message, potentially re-queue based on error handling
#         channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# async def handle_task(task: dict):
#     task_id = task["task_id"]
#     data = await get_exchange_and_routing_key(task_id)
#     if data is not None:
#         exchange = data.get("exchange")
#         routing_key = data.get("routing_key")
#         if exchange and routing_key:
#             # TODO: Send message to exchange with routing key
#             status = 0
#             for status in range(0, 100, 10):
#                 await publish_task(task_id, status, exchange, routing_key)
#                 await asyncio.sleep(1)
#     else:
#         logging.error(f"Error getting exchange and routing key for task {task_id}")


async def get_exchange_and_routing_key(ticket_id: str) -> Tuple[str, str]:
    try:
        response = await http_client.post(f"{CONTROLLER_SERVICE_URL}/service/exchange/{SERVICE_TYPE}/ticket/{ticket_id}")
        return response.json()["exchange_name"], response.json()["routing_key"]
    except Exception as e:
        logging.error(f"Error getting exchange: {e}")
        return None


# async def publish_task(task_id: str, status: int, exchange: str, routing_key: str):

#     body = {
#         "task_id": task_id,
#         "status": f"{status}%"
#     }
#     channel.basic_publish(exchange=exchange, routing_key=routing_key, body=json.dumps(body))