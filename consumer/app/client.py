import httpx
import logging
from typing import Tuple

from app.config import CONTROLLER_SERVICE_URL, CONSUMER_SERVICE_URL, SERVICE_TYPE

logger = logging.getLogger(__name__)
http_client = httpx.AsyncClient()

async def check_service_health():
    try:
        response = await http_client.get(f"{CONTROLLER_SERVICE_URL}/health")
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking service health: {e}")
        return False


async def send_register_request_and_get_queue() -> str | None:
    body = {
        "service_name": "consumer",
        "service_type": SERVICE_TYPE,
        "service_url": CONSUMER_SERVICE_URL,
        "service_description": "Consumer service"
    }
    try:
        response = await http_client.post(f"{CONTROLLER_SERVICE_URL}/service/register", json=body)
        logger.info(f"Registered service: {response.json()}")
        return response.json()["queue_name"]

    except Exception as e:
        logger.error(f"Error registering service: {e}")
        raise


async def get_exchange_and_routing_key(client_id: str) -> Tuple[str, str]:
    try:
        response = await http_client.post(f"{CONTROLLER_SERVICE_URL}/service/exchange/{SERVICE_TYPE}/client/{client_id}")
        return response.json()["exchange_name"], response.json()["routing_key"]
    except Exception as e:
        logger.error(f"Failed to get exchange info for client {client_id}: {e}")
        raise
