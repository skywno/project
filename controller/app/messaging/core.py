from aio_pika import connect_robust, RobustConnection
from aio_pika.exceptions import AMQPConnectionError
import logging
import asyncio

logger = logging.getLogger(__name__)

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
                    logger.info(f"Retrying connection in 5 seconds... (Attempt {retry_count}/{self.max_retries})")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error connecting to RabbitMQ: {e}")
                raise
        logger.error(f"Failed to connect after {self.max_retries} attempts")
        raise
