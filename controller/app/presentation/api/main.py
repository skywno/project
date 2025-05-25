from fastapi import FastAPI, Depends, HTTPException
from app.presentation.api.dependencies import get_queue_service
from app.application.services.queue_service import QueueService
from app.presentation.api.schemas.models import PublishInfo, TicketInfo
from app.presentation.api.schemas.models import ServiceRegisterRequest, ServiceRegisterResponse
from typing import List
from contextlib import asynccontextmanager
import asyncio
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

services = dict()
ticket_id = 0

http_client = httpx.AsyncClient()


health_check_task = None
health_check_running = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global health_check_running
    global health_check_task

    health_check_running = True
    health_check_task = asyncio.create_task(run_health_check())
    yield
    health_check_running = False
    if health_check_task:
        health_check_task.cancel()

async def run_health_check():   
    logger.info("Running health check task!")
    while health_check_running:
        for service_type, service in services.items():
            logger.info(f"Checking health of {service['service_name']}")
            url = service['service_url']
            logger.info(f"Checking health of {url}")
            try:
                response = await http_client.get(f"{url}/health")
                if response.status_code != 200:
                    logger.error(f"Service {service['service_name']} is not healthy")
                    services.pop(service_type)
                else:
                    logger.info(f"Service {service['service_name']} is healthy")
            except Exception as e:
                logger.error(f"Error checking health of {service['service_name']}: {e}")
                services.pop(service_type)

        logger.info("Sleeping for 20 seconds")
        await asyncio.sleep(20)

app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def check_health():
    return {"status": 200}

@app.post("/service/register")
async def register_service(req: ServiceRegisterRequest, queue_service: QueueService = Depends(get_queue_service)) -> ServiceRegisterResponse:
    try:
        services[req.service_type] = req.model_dump()
        queue_name = queue_service.create_service_request_queue(req.service_type)
        body = {"message": "Service registered successfully", "queue_name": queue_name}
        return ServiceRegisterResponse(**body)
    except Exception as e:
        logging.error(f"Error registering service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/service/types")
async def get_service_types() -> List[ServiceRegisterRequest]:
    try:
        return list(services.values())
    except Exception as e:
        logging.error(f"Error getting service types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/service/exchange/{service_type}/ticket/{ticket_id}")
async def create_service_exchange(ticket_id: int, service_type: str, queue_service: QueueService = Depends(get_queue_service)) -> PublishInfo:
    try:
        return queue_service.create_service_response_exchange(service_type, ticket_id)
    except Exception as e:
        logging.error(f"Error creating service exchange: {e}")
        raise HTTPException(status_code=500, detail=str(e))
            
@app.post("/client/exchange/{service_type}")
async def create_client_exchange(service_type: str, queue_service: QueueService = Depends(get_queue_service)) -> PublishInfo:
    try:
        return queue_service.create_client_exchange_bound_to_service_exchange(service_type)
    except Exception as e:
        logging.error(f"Error creating client exchange: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ticket")
async def create_ticket(queue_service: QueueService = Depends(get_queue_service)) -> TicketInfo:
    try:
        global ticket_id
        ticket_id += 1
        queue_name = queue_service.create_queue_for_ticket(ticket_id)
        return TicketInfo(ticket_id=ticket_id, queue_name=queue_name)
    except Exception as e:
        logging.error(f"Error creating ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))
