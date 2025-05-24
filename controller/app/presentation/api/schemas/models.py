from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class ServiceRegisterRequest(BaseModel):
    service_id: str
    service_name: str
    service_type: str

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


class ExchangeCreate(ExchangeBase):
    pass

class ExchangeUpdate(BaseModel):
    # For updates, all fields are optional as we might only update a subset.
    # Note: RabbitMQ Management API often requires delete+create for certain property changes.
    type: Optional[str] = None
    durable: Optional[bool] = None
    auto_delete: Optional[bool] = None
    arguments: Optional[Dict[str, Any]] = None

class ExchangeRead(ExchangeBase):
    # This model represents the data received from RabbitMQ's API
    vhost: str
    class Config:
        from_attributes = True # Allows Pydantic to read from ORM models or arbitrary objects

class QueueBase(BaseModel):
    name: str
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False
    arguments: Dict[str, Any] = Field(default_factory=dict) # Additional arguments for the queue

class QueueCreate(QueueBase):
    pass

class QueueUpdate(BaseModel):
    durable: Optional[bool] = None
    auto_delete: Optional[bool] = None
    exclusive: Optional[bool] = None
    arguments: Optional[Dict[str, Any]] = None

class QueueRead(QueueBase):
    vhost: str
    # RabbitMQ API might return other fields like 'messages', 'consumers', etc.
    # We only include what's relevant to our base definition.
    class Config:
        from_attributes = True

class BindingBase(BaseModel):
    source_exchange: str
    destination_type: str # "queue" or "exchange"
    destination_name: str
    routing_key: str = ""
    arguments: Dict[str, Any] | None = Field(default_factory=dict)

class BindingCreate(BindingBase):
    pass

class BindingRead(BindingBase):
    # RabbitMQ API doesn't return a simple ID for bindings,
    # so we'll use the defining characteristics.
    vhost: str | None = None
    properties_key: str | None = None # A unique identifier used by RabbitMQ internally for bindings
    class Config:
        from_attributes = True

