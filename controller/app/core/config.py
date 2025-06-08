from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Configuration settings for the operator."""
    rabbitmq_host: str = Field(
        default="rabbitmq",
        env="RABBITMQ_HOST"
    )

    rabbitmq_port: int = Field(
        default=5672,
        env="RABBITMQ_PORT"
    )
    rabbitmq_username: str = Field(
        default="admin",
        env="RABBITMQ_USERNAME"
    )
    rabbitmq_password: str = Field(
        default="admin",
        env="RABBITMQ_PASSWORD"
    )
    operator_namespace: str = Field(
        default="default",
        env="OPERATOR_NAMESPACE"
    )
    poll_interval: int = Field(
        default=30,
        env="RABBITMQ_POLL_INTERVAL_SECONDS"
    )
    keda_min_replicas: int = Field(
        default=0,
        env="KEDA_MIN_REPLICAS"
    )
    keda_max_replicas: int = Field(
        default=10,
        env="KEDA_MAX_REPLICAS"
    )
    keda_queue_length_threshold: int = Field(
        default=5,
        env="KEDA_QUEUE_LENGTH_THRESHOLD"
    )       

    model_config = SettingsConfigDict(env_file="project.env")


@lru_cache
def get_settings():
    return Settings()
