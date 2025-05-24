from fastapi import FastAPI, Depends, HTTPException
from app.presentation.api.dependencies import get_queue_service
from app.application.services.queue_service import QueueService
from app.presentation.api.schemas.models import PublishInfo, TicketInfo

import logging
import httpx
import asyncio
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

services_types = set()
ticket_id = 0

http_client = httpx.AsyncClient()

@app.post("/service/register/{service_type}")
async def register_service(service_type: str, queue_service: QueueService = Depends(get_queue_service)):
    try:
        queue_name = queue_service.create_service_request_queue(service_type)
        services_types.add(service_type)
        return {"message": "Service registered successfully", "queue_name": queue_name}
    except Exception as e:
        logging.error(f"Error registering service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/service/types")
async def get_service_types():
    try:
        return {"service_types": list(services_types)}
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
