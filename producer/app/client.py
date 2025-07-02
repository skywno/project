import httpx
import logging
import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import HTTPException
from typing import List, Dict

from app.models import Service, ExchangeInfo, TicketInfo
from app.config import CONTROLLER_SERVICE_URL

logger = logging.getLogger(__name__)

class ControllerClient:
    def __init__(self):
        self.client_id = str(uuid.uuid4())
        self._http_client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
                timeout=httpx.Timeout(10.0),
                http2=True
            )
        return self._http_client
    
    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def get_service_list(self) -> List[Service]:
        try:
            client = await self._get_client()
            response = await client.get(f"{CONTROLLER_SERVICE_URL}/service/types")
            services:List[Dict] = response.json()

            service_list = [Service(**service) for service in services]
            return service_list
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTPStatusError: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logging.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_exchange(self, service_type: str) -> ExchangeInfo:
        try:
            client = await self._get_client()
            response = await client.post(f"{CONTROLLER_SERVICE_URL}/client/exchange/{service_type}")
            logging.info(f"Exchange: {response.json()}")
            data = response.json()
            return ExchangeInfo(exchange=data.get("exchange_name"),
                                routing_key=data.get("routing_key"))
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTPStatusError: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logging.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_ticket_number_and_queue(self) -> TicketInfo:
        """Get a ticket number and queue to listen for the ticket"""
        try:
            client = await self._get_client()
            response = await client.post(f"{CONTROLLER_SERVICE_URL}/ticket?client_id={self.client_id}")
            data = response.json()
            ticket_id = str(data.get("ticket_id"))
            queue_name = data.get("queue_name")
            logger.info(f"Ticket ID: {ticket_id}, Queue Name: {queue_name}")
            return TicketInfo(ticket_id=ticket_id, queue_name=queue_name)

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTPStatusError: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logging.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))
