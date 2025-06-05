import kopf
import os
import requests
from kubernetes import client, config
import logging
import asyncio
import yaml

# --- Configuration ---

# RabbitMQ Management API details
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'http://rabbitmq.default.svc.cluster.local:15672')
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'admin')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'admin')

# Operator's namespace (where ScaledObjects will be created, and target deployments reside)
OPERATOR_NAMESPACE = os.environ.get('OPERATOR_NAMESPACE', 'default')

# Polling interval for RabbitMQ queues (in seconds)
RABBITMQ_POLL_INTERVAL_SECONDS = int(os.environ.get('RABBITMQ_POLL_INTERVAL_SECONDS', '30'))

# KEDA ScaledObject default parameters
KEDA_MIN_REPLICAS = int(os.environ.get('KEDA_MIN_REPLICAS', '0'))
KEDA_MAX_REPLICAS = int(os.environ.get('KEDA_MAX_REPLICAS', '10'))
KEDA_QUEUE_LENGTH_THRESHOLD = int(os.environ.get('KEDA_QUEUE_LENGTH_THRESHOLD', '5'))

# --- Kubernetes Client ---

_k8s_co_api = None # CustomObjectsApi for ScaledObjects
_k8s_apps_api = None # AppsV1Api for Deployments

def _get_k8s_clients():
    """Initializes and returns Kubernetes API clients."""
    global _k8s_co_api, _k8s_apps_api
    if _k8s_co_api is None or _k8s_apps_api is None:
        try:
            # Disable SSL verification before loading config
            config.load_incluster_config()
            logging.info("Loaded in-cluster Kubernetes config.")
        except config.config_exception.ConfigException:
            config.load_kube_config()
            logging.info("Loaded kubeconfig (out-of-cluster) Kubernetes config.")
        _k8s_co_api = client.CustomObjectsApi()
        _k8s_apps_api = client.AppsV1Api()

    return _k8s_co_api, _k8s_apps_api


def get_rabbitmq_queues(logger):
    """Fetches all queue names from the RabbitMQ Management API."""
    url = f"{RABBITMQ_HOST}/api/queues"
    auth = (RABBITMQ_USER, RABBITMQ_PASS)
    try:
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        queues_data = response.json()
        queue_names = {q['name'] for q in queues_data}
        logger.debug(f"Fetched {len(queue_names)} queues from RabbitMQ.")
        return queue_names
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching RabbitMQ queues from {url}: {e}")
        return set()

# --- Kubernetes Helper Functions ---

def _load_scaled_object_from_template(queue_name, target_deployment_name, scaled_object_name):
    """Loads and formats the ScaledObject template with the given parameters."""
    path = os.path.join(os.path.dirname(__file__), 'scaledobject.yaml')
    tmpl = open(path, "rt").read()    
    text = tmpl.format(
        scaled_object_name=scaled_object_name,
        operator_namespace=OPERATOR_NAMESPACE,
        queue_name=queue_name,
        target_deployment_name=target_deployment_name,
        polling_interval=RABBITMQ_POLL_INTERVAL_SECONDS,
        min_replica_count=KEDA_MIN_REPLICAS,
        max_replica_count=KEDA_MAX_REPLICAS,
        rabbitmq_host=RABBITMQ_HOST,
    )
    return yaml.safe_load(text)

def create_scaled_object(queue_name, target_deployment_name, logger):
    """Creates a KEDA ScaledObject for the given queue and target deployment."""
    co_api = _get_k8s_clients()[0]
    apps_api = _get_k8s_clients()[1]

    if not target_deployment_name:
        logger.warning(f"Could not determine target deployment for queue '{queue_name}'. Skipping ScaledObject creation.")
        return

    # Check if the target deployment actually exists
    try:
        apps_api.read_namespaced_deployment(name=target_deployment_name, namespace=OPERATOR_NAMESPACE)
        logger.info(f"Target deployment '{target_deployment_name}' found for queue '{queue_name}'.")
    except client.ApiException as e:
        if e.status == 404:
            logger.warning(f"Target deployment '{target_deployment_name}' not found for queue '{queue_name}'. Cannot create ScaledObject.")
            return
        logger.error(f"Error checking deployment '{target_deployment_name}': {e}")
        return
    
    scaled_object_name = _get_scaled_object_name(queue_name)
    data = _load_scaled_object_from_template(queue_name, target_deployment_name, scaled_object_name)

    try:
        co_api.create_namespaced_custom_object(
            group="keda.sh",
            version="v1alpha1",
            namespace=OPERATOR_NAMESPACE,
            plural="scaledobjects",
            body=data,
        )
        logger.info(f"Created ScaledObject '{scaled_object_name}' for queue '{queue_name}'.")
    except client.ApiException as e:
        if e.status == 409: # Conflict (already exists)
            logger.debug(f"ScaledObject '{scaled_object_name}' already exists.")
        else:
            logger.error(f"Error creating ScaledObject '{scaled_object_name}' for queue '{queue_name}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error creating ScaledObject '{scaled_object_name}': {e}")

def _get_scaled_object_name(queue_name):
    """Generates a consistent ScaledObject name from a queue name."""
    # Kubernetes resource names must be lowercase, alphanumeric, and start/end with an alphanumeric char.
    # Replace invalid characters with hyphens.
    return f"keda-so-{queue_name.lower().replace('.', '-').replace('_', '-')}"


def delete_scaled_object(scaled_object_name, logger):
    """Deletes a KEDA ScaledObject."""
    co_api = _get_k8s_clients()[0]
    try:
        co_api.delete_namespaced_custom_object(
            group="keda.sh",
            version="v1alpha1",
            namespace=OPERATOR_NAMESPACE,
            plural="scaledobjects",
            name=scaled_object_name,
            body=client.V1DeleteOptions()
        )
        logger.info(f"Deleted ScaledObject '{scaled_object_name}'.")
    except client.ApiException as e:
        if e.status == 404:
            logger.debug(f"ScaledObject '{scaled_object_name}' not found (already deleted?).")
        else:
            logger.error(f"Error deleting ScaledObject '{scaled_object_name}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error deleting ScaledObject '{scaled_object_name}': {e}")


def get_managed_scaled_objects(logger):
    """Fetches ScaledObjects managed by this operator."""
    co_api = _get_k8s_clients()[0]
    try:
        # We use the label we added during creation to identify our managed ScaledObjects. 
        # Check scaledobject.yaml file for the label.
        label_selector = "app.kubernetes.io/managed-by=rabbitmq-keda-operator"
        resp = co_api.list_namespaced_custom_object(
            group="keda.sh",
            version="v1alpha1",
            namespace=OPERATOR_NAMESPACE,
            plural="scaledobjects",
            label_selector=label_selector
        )
        managed_so_map = {}
        for item in resp['items']:
            queue_name = item['metadata']['labels'].get('kopf.operator.rabbitmq_queue')
            if queue_name:
                managed_so_map[queue_name] = item['metadata']['name']
        logger.debug(f"Found {len(managed_so_map)} managed ScaledObjects.")
        return managed_so_map
    except client.ApiException as e:
        logger.error(f"Error listing managed ScaledObjects: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error getting managed ScaledObjects: {e}")
        return {}

# --- Operator Handlers ---

@kopf.on.startup()
async def configure(logger, **kwargs):
    """Initial setup and client configuration."""
    _get_k8s_clients() # Initialize Kubernetes clients on startup
    logger.info("RabbitMQ KEDA Operator started.")
    logger.info(f"Monitoring RabbitMQ at: {RABBITMQ_HOST}")
    logger.info(f"Operating in Kubernetes namespace: {OPERATOR_NAMESPACE}")
    await poll_rabbitmq_queues(logger)

async def poll_rabbitmq_queues(logger):
    """
    Periodically polls RabbitMQ for new queues and manages ScaledObjects.
    """
    while True:
        logger.info("Polling RabbitMQ for queues...")
        current_rabbitmq_queues = get_rabbitmq_queues(logger)
        managed_scaled_objects = get_managed_scaled_objects(logger)

        # --- Handle new and existing queues ---
        for queue_name in current_rabbitmq_queues:
            if queue_name not in managed_scaled_objects:
                logger.info(f"New RabbitMQ queue detected: '{queue_name}'.")

                # --- CUSTOMIZE THIS MAPPING LOGIC ---
                # This is your critical logic for mapping a RabbitMQ queue to a K8s Deployment.
                # Example: Remove a common prefix "my-app-queue-" to get the deployment name.
                # If your queue is "user-queue-123", and deployment is "user-consumer-123"
                # You might need more complex logic based on your naming conventions.
                target_deployment_name = _get_target_deployment_name(logger, queue_name)

                if target_deployment_name:
                    create_scaled_object(queue_name, target_deployment_name, logger)
                else:
                    logger.debug(f"No target deployment mapping for queue: {queue_name}. Skipping ScaledObject creation.")
            else:
                logger.debug(f"Queue '{queue_name}' already has a managed ScaledObject.")

        # --- Handle deleted queues and cleanup ScaledObjects ---
        for managed_queue_name, so_name in managed_scaled_objects.items():
            if managed_queue_name not in current_rabbitmq_queues:
                logger.info(f"RabbitMQ queue '{managed_queue_name}' no longer exists. Deleting ScaledObject '{so_name}'.")
                delete_scaled_object(so_name, logger)

        logger.info("RabbitMQ queue polling complete.")
        await asyncio.sleep(RABBITMQ_POLL_INTERVAL_SECONDS)

def _get_target_deployment_name(logger, queue_name):
    if queue_name.startswith('service.request'):
        return queue_name.removeprefix('service.request.')
    else:
        logger.warning(f"No specific mapping rule for queue '{queue_name}'. Skipping creation.")
        return None
