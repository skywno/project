from kubernetes import client, config
from typing import Optional
import logging

logger = logging.getLogger(__name__)

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
            logger.info("Loaded in-cluster Kubernetes config.")
        except config.config_exception.ConfigException:
            config.load_kube_config()
            logger.info("Loaded kubeconfig (out-of-cluster) Kubernetes config.")
        
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