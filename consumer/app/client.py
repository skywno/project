import httpx
import logging
import asyncio
from typing import Tuple

from app.config import (
    CONTROLLER_SERVICE_URL, 
    CONSUMER_SERVICE_URL, 
    SERVICE_TYPE,
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE_CONNECTIONS,
    HTTP_CONNECT_TIMEOUT,
    HTTP_READ_TIMEOUT,
    HTTP_WRITE_TIMEOUT,
    HTTP_POOL_TIMEOUT
)

logger = logging.getLogger(__name__)

# Configure httpx client with proper timeout and connection pool settings
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT,  # Connection timeout
        read=HTTP_READ_TIMEOUT,     # Read timeout
        write=HTTP_WRITE_TIMEOUT,    # Write timeout
        pool=HTTP_POOL_TIMEOUT      # Pool timeout
    ),
    limits=httpx.Limits(
        max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
        max_connections=HTTP_MAX_CONNECTIONS,
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
    
    max_retries = 5
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            response = await http_client.post(f"{CONTROLLER_SERVICE_URL}/service/exchange/{SERVICE_TYPE}/client/{client_id}")
            result = (response.json()["exchange_name"], response.json()["routing_key"])
            
            # Cache the result
            _exchange_cache[client_id] = result
            logger.debug(f"Cached result for client {client_id}")
            
            return result
        except httpx.PoolTimeout as e:
            if attempt < max_retries - 1:
                logger.warning(f"Pool timeout for client {client_id}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error(f"Pool timeout for client {client_id} after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to get exchange info for client {client_id}, attempt {attempt + 1}/{max_retries}: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error(f"Failed to get exchange info for client {client_id} after {max_retries} attempts: {e}")
                raise


async def cleanup_client():
    """Clean up the httpx client when shutting down"""
    await http_client.aclose()
    _exchange_cache.clear()  # Clear the cache
    logger.info("HTTP client closed and cache cleared")


def clear_exchange_cache():
    """Clear the exchange cache manually if needed"""
    _exchange_cache.clear()
    logger.info("Exchange cache cleared")
