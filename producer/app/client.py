import httpx
import logging
import os

from fastapi import HTTPException
from typing import List, Dict
from app.models import Service, ExchangeInfo, TicketInfo

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

CONTROLLER_SERVICE_URL = os.getenv("CONTROLLER_SERVICE_URL")

class ControllerClient:

    def get_service_list(self) -> List[Service]:
        try:
            response = httpx.get(f"{CONTROLLER_SERVICE_URL}/service/types")
            services:List[Dict] = response.json()

            service_list = [Service(**service) for service in services]
            return service_list
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTPStatusError: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logging.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_exchange(self, service_type: str) -> ExchangeInfo:
        try:
            response = httpx.post(f"{CONTROLLER_SERVICE_URL}/client/exchange/{service_type}")
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
            response = httpx.post(f"{CONTROLLER_SERVICE_URL}/ticket")
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
