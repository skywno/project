import httpx
import logging
import uuid
import asyncio
from contextlib import asynccontextmanager
from aio_pika import connect_robust, RobustConnection
from aio_pika.exceptions import AMQPConnectionError
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


class RabbitMQClient:
    def __init__(self, host: str, port: int, username: str, password: str, max_retries: int = 10):
        self.url = f"amqp://{username}:{password}@{host}:{port}"
        self._connection: RobustConnection | None = None
        self.max_retries = max_retries

    async def connect(self) -> RobustConnection:
        if not self._connection:
            await self._connect_with_retry()
            logger.info(f"Connected to RabbitMQ at {self.url}")
        elif self._connection.is_closed:
            await self._connect_with_retry()
            logger.info(f"Reconnected to RabbitMQ at {self.url}")
        else:
            logger.info(f"Using existing connection to RabbitMQ at {self.url}")
        return self._connection
    
    async def disconnect(self):
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info(f"Disconnected from RabbitMQ at {self.url}")
        else:
            logger.info(f"Already disconnected from RabbitMQ at {self.url}")

    @property
    def connection(self) -> RobustConnection:
        if not self._connection:
            raise RuntimeError("Connection not established")
        return self._connection

    async def _connect_with_retry(self) -> RobustConnection:
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                self._connection = await connect_robust(self.url)
                return self._connection
            except AMQPConnectionError as e:
                retry_count += 1
                logger.error(f"Error connecting to RabbitMQ at {self.url}: {e}")
                if retry_count < self.max_retries:
                    logger.info(f"Retrying connection in 10 seconds... (Attempt {retry_count}/{self.max_retries})")
                    await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Unexpected error connecting to RabbitMQ: {e}")
                raise e
        logger.error(f"Failed to connect after {self.max_retries} attempts")
        raise Exception("Failed to connect to RabbitMQ")
