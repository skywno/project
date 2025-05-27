from fastapi import FastAPI, BackgroundTasks
import asyncio
import json
from app.client import ControllerClient
import random
import time
from app.producer import RabbitMQProducer
from app.consumer import RabbitMQConsumer
import logging
from app.models import ExchangeInfo, TicketInfo, Service
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

consumer_task: asyncio.Task | None = None

rabbitmq_consumer = RabbitMQConsumer()
rabbitmq_producer = RabbitMQProducer()
client = ControllerClient()

@app.on_event("startup")
async def startup_event():
    """FastAPI startup event to initiate RabbitMQ consumer."""
    global consumer_task
    logger.info("FastAPI startup event: Starting RabbitMQ consumer.")
    consumer_task = asyncio.create_task(rabbitmq_consumer.start_consuming())

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event to gracefully stop RabbitMQ consumer."""
    logger.info("FastAPI shutdown event: Stopping RabbitMQ consumer.")
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("RabbitMQ consumer task cancelled.")
    await rabbitmq_consumer.stop_consuming()
    logger.info("FastAPI shutdown complete.")


def create_message_payload(ticket_id):
    data = {
        "ticket_id": ticket_id,
        "user_id": "some user_id",
        "group_id": "some group id",
        "target_type": "RAG",
        "task": "do something"
    }

    return json.dumps(data)


sending_message = False
message_task = None


# async def send_message_task():
#     pass

# @app.post("/start_sending")
# async def start_sending(background_tasks: BackgroundTasks):
#     global sending_message, message_task
#     sending_message = True
#     message_task = asyncio.create_task(send_message_task())
#     return {"message": "Sending messages..."}


# @app.post("/stop_sending")
# async def stop_sending():
#     global sending_message, message_task
#     sending_message = False
#     if message_task:
#         message_task.cancel()
#         message_task = None
#     client.close()
#     return {"message": "Stopped sending messages"}

@app.post("/task")
async def task():
    services : List[Service] = client.get_service_list()
    if len(services) == 0:
        return {"message": "No services found"}
    random.shuffle(services)
    service_type = services[0].service_type
    exchange_info: ExchangeInfo = client.get_exchange(service_type)
    ticket_info: TicketInfo = client.get_ticket_number_and_queue()

    exchange_name = exchange_info.exchange
    routing_key = exchange_info.routing_key

    ticket_id = ticket_info.ticket_id
    queue_name = ticket_info.queue_name

    message = create_message_payload(ticket_id)
    await rabbitmq_consumer.add_queue(queue_name)
    rabbitmq_producer.send_message(exchange_name, ticket_id, routing_key, message)
    return {"message": "Task created"}