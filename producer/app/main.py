import asyncio
import json
import random
import logging
from fastapi import Depends, FastAPI, HTTPException
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

from datetime import datetime, timezone, timedelta
from app.client import ControllerClient, RabbitMQClient
from app.producer import RabbitMQProducer, RabbitMQProducerException
from app.consumer import RabbitMQConsumer
from app.models import ExchangeInfo, TicketInfo, Service
from app.config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USERNAME, RABBITMQ_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer_task: asyncio.Task | None = None

rabbimq_client = RabbitMQClient(RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
rabbitmq_producer = RabbitMQProducer(rabbimq_client)
rabbitmq_consumer = RabbitMQConsumer(rabbimq_client)
client = ControllerClient()

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
    
    async def get_exchange_info(self, service_type: str) -> ExchangeInfo:
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
    await rabbitmq_consumer.run()

async def shutdown_event():
    """FastAPI shutdown event to gracefully stop RabbitMQ consumer."""
    logger.info("FastAPI shutdown event: Stopping RabbitMQ consumer.")
    
    # Close HTTP client and RabbitMQ connections
    await client.close()
    await rabbitmq_producer.close()
    await rabbitmq_consumer.stop()
    
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
        exchange_info = await cache.get_exchange_info(service_type)

        exchange_name = exchange_info.exchange
        routing_key = exchange_info.routing_key
        ticket_id = ticket_info.ticket_id
        queue_name = ticket_info.queue_name

        body = create_message_payload(ticket_id)
        
        # Start consuming and send message in parallel
        await rabbitmq_consumer.start_consuming(queue_name)
        await rabbitmq_producer.send_message(
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
