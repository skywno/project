from fastapi import FastAPI, Depends, HTTPException, status
from app.core.messaging.rabbitmq import RabbitMQMgmtClient
from app.presentation.api.schemas.models import ExchangeCreate, ExchangeRead, ExchangeUpdate, QueueCreate, QueueRead, QueueUpdate, BindingCreate, BindingRead
from app.presentation.api.dependencies import get_queue_service
from app.application.services.queue_service import QueueService

app = FastAPI()

services_types = set()
ticket_id = 0
ticket_queue = {}

@app.post("/service/register/{service_type}")
async def register_service(service_type: str, queue_service: QueueService = Depends(get_queue_service)):
    queue_name = queue_service.create_service_queue(service_type)
    services_types.add(service_type)
    return {"message": "Service registered successfully", "queue_name": queue_name}

@app.get("/service/types")
async def get_service_types():
    return {"service_types": list(services_types)}

@app.post("/service/exchange/{ticket_id}")
async def create_service_exchange(ticket_id: int, service_type: str, queue_service: QueueService = Depends(get_queue_service)):
    queue_service.create_direct_exchange(f"service.response.{service_type}")
    queue_service.bind_queue_to_exchange(ticket_queue[ticket_id], f"service.response.{service_type}", f"service.response.ticket.{ticket_id}")
    return {"exchange_name": f"service.response.{service_type}", "routing_key": f"service.response.ticket.{ticket_id}"}
            
@app.post("/client/exchange/{service_type}")
async def create_client_exchange(service_type: str, queue_service: QueueService = Depends(get_queue_service)):
    client_exchange_name, routing_key = queue_service.create_client_exchange_bound_to_service_exchange(service_type)
    return {"client_exchange_name": client_exchange_name, "routing_key": routing_key}

@app.post("/ticket")
async def create_ticket(queue_service: QueueService = Depends(get_queue_service)):
    global ticket_id
    ticket_id += 1
    queue_name = queue_service.create_queue(f"ticket.{ticket_id}")
    ticket_queue[ticket_id] = queue_name
    return {"ticket_id": ticket_id, "queue_name": queue_name}
