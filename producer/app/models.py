from pydantic import BaseModel
from typing import List, Dict

class Service(BaseModel):
    service_url: str
    service_name: str
    service_type: str
    service_description: str

class ExchangeInfo(BaseModel):
    exchange: str
    routing_key: str

class TicketInfo(BaseModel):
    ticket_id: str
    queue_name: str 