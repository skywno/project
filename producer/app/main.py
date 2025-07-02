import asyncio
import json
import random
import logging
from fastapi import Depends, FastAPI, HTTPException
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

from datetime import datetime, timezone, timedelta
from app.client import ControllerClient
from app.producer import AsyncRabbitMQProducer, RabbitMQProducerException
from app.consumer import ReconnectingRabbitMQConsumer
from app.models import ExchangeInfo, TicketInfo, Service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer_task: asyncio.Task | None = None

rabbitmq_consumer = ReconnectingRabbitMQConsumer()
client = ControllerClient()
# Create a single async RabbitMQ producer instance for reuse
async_rabbitmq_producer = AsyncRabbitMQProducer()

# Simple in-memory cache for services and exchange info
class Cache:
    def __init__(self):
        self._services_cache: Optional[List[Service]] = None
        self._services_cache_time: Optional[datetime] = None
        self._exchange_cache: Dict[str, tuple[ExchangeInfo, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
        self._lock = asyncio.Lock()
    
    async def get_services(self) -> List[Service]:
        """Get services with caching."""
        async with self._lock:
            now = datetime.now()
            if (self._services_cache is None or 
                self._services_cache_time is None or 
                now - self._services_cache_time > self._cache_ttl):
                
                self._services_cache = await client.get_service_list()
                self._services_cache_time = now
                logger.info("Services cache refreshed")
            
            return self._services_cache.copy()
    
    async def get_exchange(self, service_type: str) -> ExchangeInfo:
        """Get exchange info with caching."""
        async with self._lock:
            now = datetime.now()
            cached = self._exchange_cache.get(service_type)
            
            if cached is None or now - cached[1] > self._cache_ttl:
                exchange_info = await client.get_exchange(service_type)
                self._exchange_cache[service_type] = (exchange_info, now)
                logger.info(f"Exchange cache refreshed for {service_type}")
                return exchange_info
            
            return cached[0]

# Global cache instance
cache = Cache()

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
    
    # Close HTTP client and RabbitMQ producer
    await client.close()
    await async_rabbitmq_producer.close()
    
    logger.info("FastAPI shutdown complete.")


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/task")
async def task():
    try:
        # Get services from cache and ticket info in parallel
        services_task = cache.get_services()
        ticket_task = client.get_ticket_number_and_queue()
        
        # Wait for both tasks to complete
        services, ticket_info = await asyncio.gather(
            services_task,
            ticket_task,
            return_exceptions=True
        )
        
        # Handle exceptions from parallel tasks
        if isinstance(services, Exception):
            logger.error(f"Error getting services: {services}")
            raise HTTPException(status_code=500, detail="Failed to get services")
        
        if isinstance(ticket_info, Exception):
            logger.error(f"Error getting ticket: {ticket_info}")
            raise HTTPException(status_code=500, detail="Failed to get ticket")
        
        if len(services) == 0:
            return {"message": "No services found"}
        
        random.shuffle(services)
        service_type = services[0].service_type
        
        # Get exchange info from cache
        exchange_info = await cache.get_exchange(service_type)

        exchange_name = exchange_info.exchange
        routing_key = exchange_info.routing_key
        ticket_id = ticket_info.ticket_id
        queue_name = ticket_info.queue_name

        body = create_message_payload(ticket_id)
        
        # Start consuming and send message in parallel
        rabbitmq_consumer.start_consuming(queue_name)
        await async_rabbitmq_producer.send_message(
            exchange_name, 
            client.client_id, 
            ticket_id, 
            routing_key, 
            body
        )
        
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
