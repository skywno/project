import os
from typing import Dict, Any


class DatabaseConfig:
    """Database connection and pool configuration"""
    
    MIN_CONNECTIONS = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
    MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "20"))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate database configuration"""
        if cls.MIN_CONNECTIONS < 1:
            raise ValueError("DB_MIN_CONNECTIONS must be at least 1")
        if cls.MAX_CONNECTIONS < cls.MIN_CONNECTIONS:
            raise ValueError("DB_MAX_CONNECTIONS must be >= DB_MIN_CONNECTIONS")
        return True


class BatchConfig:
    """Batch processing configuration"""
    
    SIZE = int(os.getenv("BATCH_SIZE", "100"))
    TIMEOUT = int(os.getenv("BATCH_TIMEOUT", "5"))  # seconds
    
    @classmethod
    def validate(cls) -> bool:
        """Validate batch configuration"""
        if cls.SIZE < 1:
            raise ValueError("BATCH_SIZE must be at least 1")
        if cls.TIMEOUT < 1:
            raise ValueError("BATCH_TIMEOUT must be at least 1 second")
        return True


class MemoryConfig:
    """Memory management configuration"""
    
    CLEANUP_THRESHOLD = int(os.getenv("MEMORY_CLEANUP_THRESHOLD", "1000"))
    CLEANUP_AGE = int(os.getenv("MEMORY_CLEANUP_AGE", "3600"))  # seconds (1 hour)
    
    @classmethod
    def validate(cls) -> bool:
        """Validate memory configuration"""
        if cls.CLEANUP_THRESHOLD < 1:
            raise ValueError("MEMORY_CLEANUP_THRESHOLD must be at least 1")
        if cls.CLEANUP_AGE < 60:
            raise ValueError("MEMORY_CLEANUP_AGE must be at least 60 seconds")
        return True


class LoggingConfig:
    """Logging configuration"""
    
    LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    
    @classmethod
    def validate(cls) -> bool:
        """Validate logging configuration"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if cls.LEVEL not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_levels}")
        return True


class Config:
    """Main configuration class that combines all settings"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.batch = BatchConfig()
        self.memory = MemoryConfig()
        self.logging = LoggingConfig()
        self.validate()
    
    def validate(self) -> bool:
        """Validate all configuration settings"""
        self.database.validate()
        self.batch.validate()
        self.memory.validate()
        self.logging.validate()
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging"""
        return {
            "database": {
                "min_connections": self.database.MIN_CONNECTIONS,
                "max_connections": self.database.MAX_CONNECTIONS,
            },
            "batch": {
                "size": self.batch.SIZE,
                "timeout": self.batch.TIMEOUT,
            },
            "memory": {
                "cleanup_threshold": self.memory.CLEANUP_THRESHOLD,
                "cleanup_age": self.memory.CLEANUP_AGE,
            },
            "logging": {
                "level": self.logging.LEVEL,
            }
        }


# Global configuration instance
config = Config()

# Backward compatibility exports
DB_MIN_CONNECTIONS = config.database.MIN_CONNECTIONS
DB_MAX_CONNECTIONS = config.database.MAX_CONNECTIONS
BATCH_SIZE = config.batch.SIZE
BATCH_TIMEOUT = config.batch.TIMEOUT
MEMORY_CLEANUP_THRESHOLD = config.memory.CLEANUP_THRESHOLD
MEMORY_CLEANUP_AGE = config.memory.CLEANUP_AGE
LOG_LEVEL = config.logging.LEVEL 