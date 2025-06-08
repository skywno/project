from pydantic import BaseModel, Field
from typing import Dict, Any

class ServiceRegisterRequest(BaseModel):
    service_name: str
    service_type: str
    service_description: str
    service_url: str
    
class PublishInfo(BaseModel):
    exchange_name: str
    routing_key: str

class TicketInfo(BaseModel):
    ticket_id: int
    queue_name: str

class ExchangeBase(BaseModel):
    name: str
    type: str = "topic" # e.g., "direct", "topic", "fanout", "headers"
    durable: bool = True
    auto_delete: bool = False
    arguments: Dict[str, Any] = Field(default_factory=dict) # Additional arguments for the exchange

class ServiceRegisterResponse(BaseModel):
    message: str
    queue_name: str
