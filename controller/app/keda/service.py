import os
import yaml
import logging
from kubernetes import client
from app.kubernetes.core import KubernetesClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class KedaService:  
    def __init__(self, client: KubernetesClient):
        self.settings = get_settings()
        self.client = client

    def create_scaled_object(self, queue_name, target_deployment_name, logger):
        if not target_deployment_name:
            logger.warning(f"Could not determine target deployment for queue '{queue_name}'.")
            return
        try:
            self.client.apps_api.read_namespaced_deployment(
                name=target_deployment_name,
                namespace=self.settings.operator_namespace
            )
        except client.ApiException as e:
            if e.status == 404:
                logger.warning(f"Deployment '{target_deployment_name}' not found.")
            return
        except Exception as e:
            logger.error(f"Error reading deployment: {e}")
            return

        # # NOTE: It's created earlier.
        # # Create Secret first
        # secret_name = "keda-rabbitmq-secret"
        # secret_body = self._load_secret_template(secret_name)
        # try:
        #     self.client.core_api.create_namespaced_secret(
        #         namespace=self.settings.operator_namespace,
        #         body=secret_body
        #     )
        #     logger.info(f"Created Secret '{secret_name}'.")
        # except client.ApiException as e:
        #     if e.status != 409:  # 409 means already exists
        #         logger.error(f"Error creating Secret: {e}")
        #         return

        # # Create TriggerAuthentication
        # trigger_auth_name = "keda-trigger-auth-rabbitmq-conn"
        # trigger_auth_body = self._load_trigger_auth_template(trigger_auth_name)
        # try:
        #     self.client.co_api.create_namespaced_custom_object(
        #         group="keda.sh",
        #         version="v1alpha1",
        #         namespace=self.settings.operator_namespace,
        #         plural="triggerauthentications",
        #         body=trigger_auth_body
        #     )
        #     logger.info(f"Created TriggerAuthentication '{trigger_auth_name}'.")
        # except client.ApiException as e:
        #     if e.status != 409:  # 409 means already exists
        #         logger.error(f"Error creating TriggerAuthentication: {e}")
        #         return

        # Create ScaledObject
        scaled_object_name = self._get_scaled_object_name(queue_name)
        body = self._load_scaled_object_template(queue_name, target_deployment_name, scaled_object_name)
        try:
            self.client.co_api.create_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=self.settings.operator_namespace,
                plural="scaledobjects",
                body=body
            )
            logger.info(f"Created ScaledObject '{scaled_object_name}'.")
        except client.ApiException as e:
            if e.status != 409:
                logger.error(f"Error creating ScaledObject: {e}")

    def _get_scaled_object_name(self, queue_name: str) -> str:
        """Generate a consistent ScaledObject name from a queue name."""
        return f"keda-so-{queue_name.lower().replace('.', '-').replace('_', '-')}"

    def _load_secret_template(self, secret_name):
        path = os.path.join(os.path.dirname(__file__), 'templates/secret.yaml')
        with open(path, "rt") as f:
            tmpl = f.read()
        text = tmpl.format(
            operator_namespace=self.settings.operator_namespace,
            username=self.settings.rabbitmq_username,
            password=self.settings.rabbitmq_password,
            host=self.settings.rabbitmq_host,
            port=self.settings.rabbitmq_port
        )
        return yaml.safe_load(text)

    def _load_trigger_auth_template(self, trigger_auth_name):
        path = os.path.join(os.path.dirname(__file__), 'templates/trigger-auth.yaml')
        with open(path, "rt") as f:
            tmpl = f.read()
        text = tmpl.format(
            operator_namespace=self.settings.operator_namespace
        )
        return yaml.safe_load(text)

    def _load_scaled_object_template(self, queue_name, target_deployment_name, scaled_object_name):
        path = os.path.join(os.path.dirname(__file__), 'templates/scaledobject.yaml')
        with open(path, "rt") as f:
            tmpl = f.read()
        text = tmpl.format(
            scaled_object_name=scaled_object_name,
            operator_namespace=self.settings.operator_namespace,
            queue_name=queue_name,
            target_deployment_name=target_deployment_name,
            polling_interval=self.settings.poll_interval,
            cooldown_period=self.settings.cooldown_period,
            min_replica_count=self.settings.keda_min_replicas,
            max_replica_count=self.settings.keda_max_replicas,
        )
        return yaml.safe_load(text)

    def delete_scaled_object(self, scaled_object_name):
        try:
            self.client.co_api.delete_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=self.settings.operator_namespace,
                plural="scaledobjects",
                name=scaled_object_name,
                body=client.V1DeleteOptions()
            )
            logger.info(f"Deleted ScaledObject '{scaled_object_name}'.")
        except client.ApiException as e:
            if e.status != 404:
                logger.error(f"Error deleting ScaledObject: {e}")

    def get_managed_scaled_objects(self):
        try:
            resp = self.client.co_api.list_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=self.settings.operator_namespace,
                plural="scaledobjects",
                label_selector="app.kubernetes.io/managed-by=rabbitmq-keda-operator"
            )
            return {
                item['metadata']['labels'].get('kopf.operator.rabbitmq_queue'): item['metadata']['name']
                for item in resp['items']
                if 'kopf.operator.rabbitmq_queue' in item['metadata']['labels']
            }
        except Exception as e:
            logger.error(f"Error fetching managed ScaledObjects: {e}")
            return {}
