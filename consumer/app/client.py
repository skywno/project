import httpx
import logging
from typing import Tuple

from app.config import CONTROLLER_SERVICE_URL, CONSUMER_SERVICE_URL, SERVICE_TYPE

logger = logging.getLogger(__name__)

# Configure httpx client with proper timeout and connection pool settings
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=10.0,  # Connection timeout
        read=30.0,     # Read timeout
        write=10.0,    # Write timeout
        pool=30.0      # Pool timeout
    ),
    limits=httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10,
        keepalive_expiry=30.0
    ),
    http2=False  # Disable HTTP/2 if causing issues
)

# Cache for exchange and routing key results
_exchange_cache = {}

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
    # Check cache first
    if client_id in _exchange_cache:
        logger.debug(f"Cache hit for client {client_id}")
        return _exchange_cache[client_id]
    
    try:
        response = await http_client.post(f"{CONTROLLER_SERVICE_URL}/service/exchange/{SERVICE_TYPE}/client/{client_id}")
        result = (response.json()["exchange_name"], response.json()["routing_key"])
        
        # Cache the result
        _exchange_cache[client_id] = result
        logger.debug(f"Cached result for client {client_id}")
        
        return result
    except Exception as e:
        logger.error(f"Failed to get exchange info for client {client_id}: {e}")
        raise


async def cleanup_client():
    """Clean up the httpx client when shutting down"""
    await http_client.aclose()
    logger.info("HTTP client closed")
