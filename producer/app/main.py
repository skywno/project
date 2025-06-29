import asyncio
import json
import random
import logging
from fastapi import Depends, FastAPI, HTTPException
from typing import List
from contextlib import asynccontextmanager

from datetime import datetime, timezone
from app.client import ControllerClient
from app.producer import RabbitMQProducer, RabbitMQProducerException
from app.consumer import ReconnectingRabbitMQConsumer
from app.models import ExchangeInfo, TicketInfo, Service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer_task: asyncio.Task | None = None

rabbitmq_consumer = ReconnectingRabbitMQConsumer()
client = ControllerClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield
    await shutdown_event()

async def startup_event():
    """FastAPI startup event to initiate RabbitMQ consumer."""
    global consumer_task
    logger.info("FastAPI startup event: Starting RabbitMQ consumer.")
    consumer_task = asyncio.create_task(rabbitmq_consumer.run())

async def shutdown_event():
    """FastAPI shutdown event to gracefully stop RabbitMQ consumer."""
    logger.info("FastAPI shutdown event: Stopping RabbitMQ consumer.")
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled.")
        except Exception as e:
            logger.error(f"Error in consumer task: {e}")
    logger.info("FastAPI shutdown complete.")


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/task")
async def task():
    try:
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

        body = create_message_payload(ticket_id)
        rabbitmq_consumer.start_consuming(queue_name)
        with RabbitMQProducer() as rabbitmq_producer:
            rabbitmq_producer.send_message(exchange_name, client.client_id, ticket_id, routing_key, body)
        return {"message": "Task created", "ticket_id": ticket_id}
    except RabbitMQProducerException as e:
        logger.error(f"Error while sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error in task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def create_message_payload(ticket_id):
    data = {
        "task": "do something",
        "request_submission_time": datetime.now(timezone.utc).isoformat()
    }

    return json.dumps(data)
