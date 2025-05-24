import httpx 
from typing import Dict, Any, Optional, List
from fastapi import HTTPException

# --- 3. RabbitMQ Management API Client ---
class RabbitMQMgmtClient:
    """Client for interacting with the RabbitMQ Management HTTP API."""
    def __init__(self, base_url: str, user: str, password: str, vhost: str):
        self.base_url = base_url
        self.auth = (user, password)
        self.vhost = vhost
        # httpx.AsyncClient is created once and reused for performance
        self.client = httpx.AsyncClient(base_url=base_url, auth=self.auth, timeout=30.0)

    async def _request(self, method: str, path: str, **kwargs):
        """
        Helper for making HTTP requests to RabbitMQ API.
        Handles common errors and returns JSON response.
      create_queue  """
        try:
            response = await self.client.request(method, path, **kwargs)
            response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
            return response.json()
        except httpx.HTTPStatusError as e:
            # Log the full error from RabbitMQ for debugging
            print(f"HTTP error for {method} {path}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            # Handle network or connection errors
            print(f"Request error for {method} {path}: {e}")
            raise HTTPException(status_code=500, detail=f"RabbitMQ connection error: {e}")

    # --- Exchanges ---
    async def get_all_exchanges(self) -> List[Dict[str, Any]]:
        """Fetches all exchanges for the configured virtual host from RabbitMQ."""
        # The /api/exchanges/{vhost} endpoint returns exchanges for a specific vhost
        return await self._request("GET", f"/api/exchanges/{self.vhost}")

    async def get_exchange(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetches a single exchange by name from RabbitMQ."""
        try:
            return await self._request("GET", f"/api/exchanges/{self.vhost}/{name}")
        except HTTPException as e:
            if e.status_code == 404:
                return None # Exchange not found
            raise # Re-raise other HTTP exceptions

    async def create_exchange(self, name: str, data: Dict[str, Any]):
        """Creates an exchange in RabbitMQ."""
        # RabbitMQ PUT for exchanges is idempotent; it creates if not exists,
        # or updates if it exists and properties allow (some require delete+create).
        await self._request("PUT", f"/api/exchanges/{self.vhost}/{name}", json=data)

    async def delete_exchange(self, name: str):
        """Deletes an exchange from RabbitMQ."""
        await self._request("DELETE", f"/api/exchanges/{self.vhost}/{name}")

    # --- Queues ---
    async def get_all_queues(self) -> List[Dict[str, Any]]:
        """Fetches all queues for the configured virtual host from RabbitMQ."""
        return await self._request("GET", f"/api/queues/{self.vhost}")

    async def get_queue(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetches a single queue by name from RabbitMQ."""
        try:
            return await self._request("GET", f"/api/queues/{self.vhost}/{name}")
        except HTTPException as e:
            if e.status_code == 404:
                return None # Queue not found
            raise # Re-raise other HTTP exceptions

    async def create_queue(self, name: str, data: Dict[str, Any]):
        """Creates a queue in RabbitMQ."""
        await self._request("PUT", f"/api/queues/{self.vhost}/{name}", json=data)

    async def delete_queue(self, name: str):
        """Deletes a queue from RabbitMQ."""
        await self._request("DELETE", f"/api/queues/{self.vhost}/{name}")

    # --- Bindings ---
    async def get_all_bindings(self) -> List[Dict[str, Any]]:
        """Fetches all bindings for the configured virtual host from RabbitMQ."""
        return await self._request("GET", f"/api/bindings/{self.vhost}")

    async def create_binding(self, source: str, destination_type: str, destination: str, routing_key: str, arguments: Dict[str, Any]):
        """Creates a binding in RabbitMQ."""
        # RabbitMQ binding API path is specific: /api/bindings/{vhost}/e/{exchange}/q/{queue} or /api/bindings/{vhost}/e/{exchange}/e/{exchange}
        path = f"/api/bindings/{self.vhost}/e/{source}/{destination_type}/{destination}"
        # The POST request body for creating a binding only needs routing_key and arguments
        await self._request("POST", path, json={"routing_key": routing_key, "arguments": arguments})

    async def delete_binding(self, source: str, destination_type: str, destination: str, routing_key: str):
        """Deletes a binding from RabbitMQ."""
        # Deleting a binding requires a DELETE request to a specific path
        # and sometimes a body with routing_key and arguments for exact match.
        # The path is /api/bindings/{vhost}/e/{source}/{destination_type}/{destination}/{properties_key}
        # where properties_key is a URL-encoded string of routing_key and arguments.
        # For simplicity, we'll use the direct DELETE endpoint which requires the properties_key.
        # A more robust solution would fetch the binding first to get its properties_key.
        # For now, we'll use the direct path that assumes a simple routing key.
        
        # RabbitMQ binding properties_key is URL-encoded routing_key~URL-encoded_arguments_json
        # For simple routing keys with no arguments, it's often just the routing_key itself.
        # For a truly robust delete, you'd list bindings and match all components.
        # Here, we'll construct the properties_key assuming simple cases or direct match.
        
        # If arguments are empty, properties_key is just routing_key
        # If arguments exist, it's routing_key~json.dumps(arguments)
        # This is a simplification. For full robustness, you'd iterate get_all_bindings()
        # to find the exact properties_key.
        
        # Let's simplify for the demo and assume the routing_key is the primary identifier for deletion
        # This might not work for bindings with identical routing keys but different arguments.
        # The RabbitMQ API for DELETE /api/bindings/{vhost}/{exchange}/{destination_type}/{destination}/{properties_key}
        # requires the properties_key which is a URL-encoded form of routing_key and arguments.
        
        # A more practical approach for deletion without a DB ID:
        # 1. Fetch all bindings from source to destination.
        # 2. Find the specific binding by matching routing_key and arguments.
        # 3. Use its 'properties_key' to delete.
        
        # For this direct management system, we'll make delete_binding more explicit:
        # It will require the properties_key from the client, which they would get from a read operation.
        # Or, we can list all bindings and find the matching one. Let's do the latter for user convenience.
        
        all_bindings = await self.get_all_bindings()
        binding_to_delete = None
        for b in all_bindings:
            if (b['source'] == source and
                b['destination_type'] == destination_type and
                b['destination'] == destination and
                b['routing_key'] == routing_key):
                # Note: arguments also need to match for a precise binding delete, but for simplicity
                # we're omitting deep comparison of arguments here.
                binding_to_delete = b
                break
        
        if not binding_to_delete:
            raise HTTPException(status_code=404, detail="Binding not found in RabbitMQ for deletion.")

        # The path for DELETE is /api/bindings/{vhost}/e/{source_exchange}/{destination_type}/{destination_name}/{properties_key}
        # properties_key is a URL-encoded string of the routing key and arguments.
        # RabbitMQ Management API returns 'properties_key' in the binding objects.
        delete_path = f"/api/bindings/{self.vhost}/e/{source}/{destination_type}/{destination}/{binding_to_delete['properties_key']}"
        await self._request("DELETE", delete_path)

import pika

class RabbitMQPikaClient:

    def __init__(self, host: str = None, port: int = None, username: str = None, password: str = None):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=pika.PlainCredentials(username, password)
            )
        )
        self.channel = self.connection.channel()

    def close(self):
        self.connection.close()

    def __del__(self):
        self.close()
