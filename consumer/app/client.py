import requests
import logging
import asyncio
from typing import Tuple

from app.config import (
    CONTROLLER_SERVICE_URL, 
    CONSUMER_SERVICE_URL, 
    SERVICE_TYPE,
    HTTP_CONNECT_TIMEOUT,
    HTTP_READ_TIMEOUT
)

logger = logging.getLogger(__name__)

# Configure requests session with proper timeout settings
http_session = requests.Session()
http_session.timeout = (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)

# Cache for exchange and routing key results
_exchange_cache = {}

def check_service_health():
    try:
        response = http_session.get(f"{CONTROLLER_SERVICE_URL}/health")
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking service health: {e}")
        return False


def send_register_request_and_get_queue() -> str | None:
    body = {
        "service_name": "consumer",
        "service_type": SERVICE_TYPE,
        "service_url": CONSUMER_SERVICE_URL,
        "service_description": "Consumer service"
    }
    try:
        response = http_session.post(f"{CONTROLLER_SERVICE_URL}/service/register", json=body)
        logger.info(f"Registered service: {response.json()}")
        return response.json()["queue_name"]

    except Exception as e:
        logger.error(f"Error registering service: {e}")
        raise


def get_exchange_and_routing_key(client_id: str) -> Tuple[str, str]:
    # Check cache first
    if client_id in _exchange_cache:
        logger.debug(f"Cache hit for client {client_id}")
        return _exchange_cache[client_id]
    
    max_retries = 5
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            response = http_session.post(f"{CONTROLLER_SERVICE_URL}/service/exchange/{SERVICE_TYPE}/client/{client_id}")
            result = (response.json()["exchange_name"], response.json()["routing_key"])
            
            # Cache the result
            _exchange_cache[client_id] = result
            logger.debug(f"Cached result for client {client_id}")
            
            return result
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout for client {client_id}, attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error(f"Timeout for client {client_id} after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to get exchange info for client {client_id}, attempt {attempt + 1}/{max_retries}: {e}. Retrying in {retry_delay}s...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error(f"Failed to get exchange info for client {client_id} after {max_retries} attempts: {e}")
                raise


def cleanup_client():
    """Clean up the requests session when shutting down"""
    http_session.close()
    _exchange_cache.clear()  # Clear the cache
    logger.info("HTTP session closed and cache cleared")


def clear_exchange_cache():
    """Clear the exchange cache manually if needed"""
    _exchange_cache.clear()
    logger.info("Exchange cache cleared")
