import httpx
import logging

from fastapi import HTTPException
from typing import List, Dict
from app.models import ServiceList, ExchangeInfo, TicketInfo

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

class ControllerClient:

    def get_service_list(self) -> ServiceList:
        try:
            response = httpx.get("http://controller:8000/service/types")
            services = response.json()
            return ServiceList(types=services.get("service_types"))
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTPStatusError: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logging.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_exchange(self, service_type: str) -> ExchangeInfo:
        try:
            response = httpx.post(f"http://controller:8000/client/exchange/{service_type}")
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

    def get_ticket_number_and_queue(self) -> TicketInfo:
        """Get a ticket number and queue to listen for the ticket"""
        try:
            response = httpx.post(f"http://controller:8000/ticket")
            data = response.json()
            ticket_id = str(data.get("ticket_id"))
            queue_name = data.get("queue_name")
            return TicketInfo(ticket_id=ticket_id, queue_name=queue_name)

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTPStatusError: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logging.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))
