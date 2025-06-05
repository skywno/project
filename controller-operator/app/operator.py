from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
import kopf
import os
import requests
from kubernetes import client, config
import logging
import asyncio
import yaml

@dataclass
class Config:
    """Configuration settings for the operator."""
    rabbitmq_host: str = os.environ.get('RABBITMQ_HOST', 'http://rabbitmq.default.svc.cluster.local:15672')
    rabbitmq_user: str = os.environ.get('RABBITMQ_USER', 'admin')
    rabbitmq_pass: str = os.environ.get('RABBITMQ_PASS', 'admin')
    operator_namespace: str = os.environ.get('OPERATOR_NAMESPACE', 'default')
    poll_interval: int = int(os.environ.get('RABBITMQ_POLL_INTERVAL_SECONDS', '30'))
    keda_min_replicas: int = int(os.environ.get('KEDA_MIN_REPLICAS', '0'))
    keda_max_replicas: int = int(os.environ.get('KEDA_MAX_REPLICAS', '10'))
    keda_queue_length_threshold: int = int(os.environ.get('KEDA_QUEUE_LENGTH_THRESHOLD', '5'))

class KubernetesClient:
    """Manages Kubernetes API client connections."""
    def __init__(self):
        self._co_api: Optional[client.CustomObjectsApi] = None
        self._apps_api: Optional[client.AppsV1Api] = None
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize Kubernetes API clients."""
        try:
            config.load_incluster_config()
            logging.info("Loaded in-cluster Kubernetes config.")
        except config.config_exception.ConfigException:
            config.load_kube_config()
            logging.info("Loaded kubeconfig (out-of-cluster) Kubernetes config.")
        
        self._co_api = client.CustomObjectsApi()
        self._apps_api = client.AppsV1Api()

    @property
    def co_api(self) -> client.CustomObjectsApi:
        """Get the CustomObjectsApi client."""
        if not self._co_api:
            self._initialize_clients()
        return self._co_api

    @property
    def apps_api(self) -> client.AppsV1Api:
        """Get the AppsV1Api client."""
        if not self._apps_api:
            self._initialize_clients()
        return self._apps_api

class RabbitMQClient:
    """Handles RabbitMQ API interactions."""
    def __init__(self, config: Config):
        self.config = config

    def get_queues(self, logger: logging.Logger) -> Set[str]:
        """Fetch all queue names from RabbitMQ Management API."""
        url = f"{self.config.rabbitmq_host}/api/queues"
        auth = (self.config.rabbitmq_user, self.config.rabbitmq_pass)
        
        try:
            response = requests.get(url, auth=auth, timeout=10)
            response.raise_for_status()
            queues_data = response.json()
            queue_names = {q['name'] for q in queues_data}
            logger.debug(f"Fetched {len(queue_names)} queues from RabbitMQ.")
            return queue_names
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching RabbitMQ queues from {url}: {e}")
            return set()

class KEDAOperator:
    """Manages KEDA ScaledObject operations."""
    def __init__(self, config: Config, k8s_client: KubernetesClient):
        self.config = config
        self.k8s_client = k8s_client

    def _load_scaled_object_template(self, queue_name: str, target_deployment_name: str, scaled_object_name: str) -> dict:
        """Load and format the ScaledObject template."""
        path = os.path.join(os.path.dirname(__file__), 'scaledobject.yaml')
        with open(path, "rt") as f:
            tmpl = f.read()
        
        text = tmpl.format(
            scaled_object_name=scaled_object_name,
            operator_namespace=self.config.operator_namespace,
            queue_name=queue_name,
            target_deployment_name=target_deployment_name,
            polling_interval=self.config.poll_interval,
            min_replica_count=self.config.keda_min_replicas,
            max_replica_count=self.config.keda_max_replicas,
            rabbitmq_host=self.config.rabbitmq_host,
        )
        return yaml.safe_load(text)

    def create_scaled_object(self, queue_name: str, target_deployment_name: str, logger: logging.Logger) -> None:
        """Create a KEDA ScaledObject for the given queue and target deployment."""
        if not target_deployment_name:
            logger.warning(f"Could not determine target deployment for queue '{queue_name}'. Skipping ScaledObject creation.")
            return

        try:
            self.k8s_client.apps_api.read_namespaced_deployment(
                name=target_deployment_name,
                namespace=self.config.operator_namespace
            )
            logger.info(f"Target deployment '{target_deployment_name}' found for queue '{queue_name}'.")
        except client.ApiException as e:
            if e.status == 404:
                logger.warning(f"Target deployment '{target_deployment_name}' not found for queue '{queue_name}'.")
                return
            logger.error(f"Error checking deployment '{target_deployment_name}': {e}")
            return

        scaled_object_name = self._get_scaled_object_name(queue_name)
        data = self._load_scaled_object_template(queue_name, target_deployment_name, scaled_object_name)

        try:
            self.k8s_client.co_api.create_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=self.config.operator_namespace,
                plural="scaledobjects",
                body=data,
            )
            logger.info(f"Created ScaledObject '{scaled_object_name}' for queue '{queue_name}'.")
        except client.ApiException as e:
            if e.status == 409:
                logger.debug(f"ScaledObject '{scaled_object_name}' already exists.")
            else:
                logger.error(f"Error creating ScaledObject '{scaled_object_name}': {e}")

    def delete_scaled_object(self, scaled_object_name: str, logger: logging.Logger) -> None:
        """Delete a KEDA ScaledObject."""
        try:
            self.k8s_client.co_api.delete_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=self.config.operator_namespace,
                plural="scaledobjects",
                name=scaled_object_name,
                body=client.V1DeleteOptions()
            )
            logger.info(f"Deleted ScaledObject '{scaled_object_name}'.")
        except client.ApiException as e:
            if e.status == 404:
                logger.debug(f"ScaledObject '{scaled_object_name}' not found.")
            else:
                logger.error(f"Error deleting ScaledObject '{scaled_object_name}': {e}")

    def get_managed_scaled_objects(self, logger: logging.Logger) -> Dict[str, str]:
        """Fetch ScaledObjects managed by this operator."""
        try:
            label_selector = "app.kubernetes.io/managed-by=rabbitmq-keda-operator"
            resp = self.k8s_client.co_api.list_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=self.config.operator_namespace,
                plural="scaledobjects",
                label_selector=label_selector
            )
            managed_so_map = {
                item['metadata']['labels'].get('kopf.operator.rabbitmq_queue'): item['metadata']['name']
                for item in resp['items']
                if 'kopf.operator.rabbitmq_queue' in item['metadata']['labels']
            }
            logger.debug(f"Found {len(managed_so_map)} managed ScaledObjects.")
            return managed_so_map
        except Exception as e:
            logger.error(f"Error getting managed ScaledObjects: {e}")
            return {}

    @staticmethod
    def _get_scaled_object_name(queue_name: str) -> str:
        """Generate a consistent ScaledObject name from a queue name."""
        return f"keda-so-{queue_name.lower().replace('.', '-').replace('_', '-')}"

class QueueDeploymentMapper:
    """Maps RabbitMQ queues to Kubernetes deployments."""
    @staticmethod
    def get_target_deployment_name(logger: logging.Logger, queue_name: str) -> Optional[str]:
        """Map a queue name to a target deployment name."""
        if queue_name.startswith('service.request'):
            return queue_name.removeprefix('service.request.')
        logger.warning(f"No specific mapping rule for queue '{queue_name}'. Skipping creation.")
        return None

class RabbitMQKEDAOperator:
    """Main operator class that coordinates all operations."""
    def __init__(self):
        self.config = Config()
        self.k8s_client = KubernetesClient()
        self.rabbitmq_client = RabbitMQClient(self.config)
        self.keda_operator = KEDAOperator(self.config, self.k8s_client)
        self.queue_mapper = QueueDeploymentMapper()

    async def poll_rabbitmq_queues(self, logger: logging.Logger) -> None:
        """Periodically poll RabbitMQ for new queues and manage ScaledObjects."""
        while True:
            logger.info("Polling RabbitMQ for queues...")
            current_queues = self.rabbitmq_client.get_queues(logger)
            managed_objects = self.keda_operator.get_managed_scaled_objects(logger)

            # Handle new and existing queues
            for queue_name in current_queues:
                if queue_name not in managed_objects:
                    logger.info(f"New RabbitMQ queue detected: '{queue_name}'.")
                    target_deployment = self.queue_mapper.get_target_deployment_name(logger, queue_name)
                    if target_deployment:
                        self.keda_operator.create_scaled_object(queue_name, target_deployment, logger)
                else:
                    logger.debug(f"Queue '{queue_name}' already has a managed ScaledObject.")

            # Handle deleted queues
            for managed_queue, so_name in managed_objects.items():
                if managed_queue not in current_queues:
                    logger.info(f"RabbitMQ queue '{managed_queue}' no longer exists. Deleting ScaledObject '{so_name}'.")
                    self.keda_operator.delete_scaled_object(so_name, logger)

            logger.info("RabbitMQ queue polling complete.")
            await asyncio.sleep(self.config.poll_interval)

# --- Operator Handlers ---

@kopf.on.startup()
async def configure(logger: logging.Logger, **kwargs) -> None:
    """Initial setup and client configuration."""
    operator = RabbitMQKEDAOperator()
    logger.info("RabbitMQ KEDA Operator started.")
    logger.info(f"Monitoring RabbitMQ at: {operator.config.rabbitmq_host}")
    logger.info(f"Operating in Kubernetes namespace: {operator.config.operator_namespace}")
    await operator.poll_rabbitmq_queues(logger)
