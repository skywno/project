from pydantic import BaseModel
from typing import List, Dict

class ServiceList(BaseModel):
    types: List[str]

class ExchangeInfo(BaseModel):
    exchange: str
    routing_key: str

class TicketInfo(BaseModel):
    ticket_id: str
    queue_name: str 