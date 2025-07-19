from __future__ import annotations  
from psycopg2 import pool
from psycopg2.extras import Json, execute_batch
import os
import logging
from datetime import datetime, timezone
from collections import deque
import threading
import time
from typing import Dict, List, Tuple, Optional, Any
from app.config import config
from app.performance_monitor import performance_monitor, monitor_operation

<<<<<<< Updated upstream
logging.basicConfig(level=getattr(logging, config.logging.LEVEL))
=======
logging.basicConfig(level=getattr(logging, config.logging.LEVEL), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
>>>>>>> Stashed changes
logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Manages database connection pool with optimized settings"""
    
    def __init__(self):
<<<<<<< Updated upstream
        self.pool = pool.SimpleConnectionPool(
            minconn=config.database.MIN_CONNECTIONS,
            maxconn=config.database.MAX_CONNECTIONS,
            host=os.getenv("POSTGRES_HOST"),
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            port=os.getenv("POSTGRES_PORT")
        )
    
    def get_connection(self):
        return self.pool.getconn()
    
    def release_connection(self, conn):
        self.pool.putconn(conn)


class BatchProcessor:
    """Handles batched database operations for better performance"""
    
    def __init__(self, db_operations: DatabaseOperations):
        self.db_operations = db_operations
        self.event_logs_batch = deque()
        self.batch_lock = threading.Lock()
        self._start_background_processor()
    
    def _start_background_processor(self):
        """Start background thread for processing batches"""
        batch_thread = threading.Thread(target=self._process_batches, daemon=True)
        batch_thread.start()
    
    def _process_batches(self):
        """Background thread that processes batched operations"""
        while True:
            try:
                time.sleep(config.batch.TIMEOUT)
                self._process_event_logs_batch()
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
    
    def _process_event_logs_batch(self):
        """Process event_logs batch if there are items"""
        with self.batch_lock:
            if len(self.event_logs_batch) > 0:
                batch_data = list(self.event_logs_batch)
                self.event_logs_batch.clear()
                
                if batch_data:
                    self._execute_batch_event_logs(batch_data)
    
    @monitor_operation("batch_event_logs")
    def _execute_batch_event_logs(self, batch_data: List[Tuple]):
        """Execute batch insert for event_logs"""
        def batch_insert(cursor):
            execute_batch(cursor, """
                INSERT INTO event_logs (ticket_id, event_type, user_id, group_id, target_type, data) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, batch_data, page_size=100)
        
        self.db_operations.execute_db_operation(batch_insert, "Batch event_logs insert", batch_mode=True)
    
    def add_to_event_logs_batch(self, data: Tuple):
        """Add data to event_logs batch queue"""
        with self.batch_lock:
            self.event_logs_batch.append(data)
            
            # Process immediately if batch is full
            if len(self.event_logs_batch) >= config.batch.SIZE:
                batch_data = list(self.event_logs_batch)
                self.event_logs_batch.clear()
                self._execute_batch_event_logs(batch_data)


class MemoryManager:
    """Manages in-memory storage with automatic cleanup"""
    
    def __init__(self):
        self.prompt_response_in_memory: Dict[str, Dict] = {}
        self.memory_lock = threading.Lock()
    
    def get_or_create_ticket_data(self, ticket_id: str) -> Dict:
        """Get existing ticket data or create new entry"""
        with self.memory_lock:
            if ticket_id not in self.prompt_response_in_memory:
                self.prompt_response_in_memory[ticket_id] = {
                    "tokens": [],
                    "service_processing_last_update_time": None,
                    "created_at": time.time()
                }
            return self.prompt_response_in_memory[ticket_id]
    
    def update_ticket_data(self, ticket_id: str, **updates):
        """Update ticket data with thread safety"""
        with self.memory_lock:
            if ticket_id in self.prompt_response_in_memory:
                self.prompt_response_in_memory[ticket_id].update(updates)
    
    def remove_ticket_data(self, ticket_id: str):
        """Remove ticket data from memory"""
        with self.memory_lock:
            if ticket_id in self.prompt_response_in_memory:
                del self.prompt_response_in_memory[ticket_id]
    
    def cleanup_old_entries(self):
        """Clean up old memory entries to prevent memory leaks"""
        current_time = time.time()
        with self.memory_lock:
            keys_to_remove = [
                ticket_id for ticket_id, data in self.prompt_response_in_memory.items()
                if current_time - data.get('created_at', current_time) > config.memory.CLEANUP_AGE
            ]
            
            for key in keys_to_remove:
                del self.prompt_response_in_memory[key]
    
    def should_cleanup(self) -> bool:
        """Check if cleanup should be performed"""
        return len(self.prompt_response_in_memory) > config.memory.CLEANUP_THRESHOLD


class DatabaseOperations:
    """Handles core database operations with connection management"""
    
    def __init__(self, connection_pool: DatabaseConnectionPool):
        self.connection_pool = connection_pool
    
    def execute_db_operation(self, operation_func, operation_name: str = "Database operation", batch_mode: bool = True):
        """
        Generic function to handle database operations with proper connection management.
        
        Args:
            operation_func: Function that takes a cursor and performs the database operation
            operation_name: Name of the operation for logging purposes
            batch_mode: If True, don't commit immediately (for batch operations)
        """
        conn = self.connection_pool.get_connection()
        cursor = conn.cursor()
        try:
            operation_func(cursor)
            if not batch_mode:
                conn.commit()
            rows_affected = cursor.rowcount
            logger.debug(f"Operation affected {rows_affected} rows")
            logger.debug(f"{operation_name} completed successfully")
        except Exception as e:
            logger.error(f"Database error: {e}")
            if not batch_mode:
                conn.rollback()
            raise
        finally:
            cursor.close()
            self.connection_pool.release_connection(conn)


class DataSaver:
    """Main class for saving data with optimized performance"""
    
    def __init__(self):
=======
        logger.info("Initializing database connection pool...")
        
        # Log database configuration (without sensitive data)
        host = os.getenv("POSTGRES_HOST")
        dbname = os.getenv("POSTGRES_DB")
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        port = os.getenv("POSTGRES_PORT")
        
        logger.info(f"Database: {dbname}@{host}:{port}")
        
        if not all([host, dbname, user, password, port]):
            logger.error("Missing required database environment variables!")
            logger.error("Please set: POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_PORT")
            raise ValueError("Missing required database environment variables")
        
        try:
            self.pool = pool.SimpleConnectionPool(
                minconn=config.database.MIN_CONNECTIONS,
                maxconn=config.database.MAX_CONNECTIONS,
                host=host,
                dbname=dbname,
                user=user,
                password=password,
                port=port
            )
            logger.info(f"Database connection pool created successfully with {config.database.MIN_CONNECTIONS}-{config.database.MAX_CONNECTIONS} connections")
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise
    
    def get_connection(self):
        return self.pool.getconn()
    
    def release_connection(self, conn):
        self.pool.putconn(conn)


class BatchProcessor:
    """Handles batched database operations for better performance"""
    
    def __init__(self, db_operations: DatabaseOperations):
        logger.info("Initializing batch processor...")
        self.db_operations = db_operations
        self.event_logs_batch = deque()
        self.batch_lock = threading.Lock()
        logger.info(f"Batch processor initialized with batch size: {config.batch.SIZE}, timeout: {config.batch.TIMEOUT}s")
        self._start_background_processor()
    
    def _start_background_processor(self):
        """Start background thread for processing batches"""
        logger.info("Starting background batch processor thread...")
        batch_thread = threading.Thread(target=self._process_batches, daemon=True)
        batch_thread.start()
        logger.info("Background batch processor thread started")
    
    def _process_batches(self):
        """Background thread that processes batched operations"""
        logger.info("Background batch processor started, waiting for batches...")
        while True:
            try:
                time.sleep(config.batch.TIMEOUT)
                self._process_event_logs_batch()
            except Exception as e:
                logger.error(f"Error in batch processing: {e}", exc_info=True)
    
    def _process_event_logs_batch(self):
        """Process event_logs batch if there are items"""
        with self.batch_lock:
            batch_size = len(self.event_logs_batch)
            if batch_size > 0:
                logger.info(f"Processing batch of {batch_size} event_logs...")
                batch_data = list(self.event_logs_batch)
                self.event_logs_batch.clear()
                
                if batch_data:
                    self._execute_batch_event_logs(batch_data)
    
    @monitor_operation("batch_event_logs")
    def _execute_batch_event_logs(self, batch_data: List[Tuple]):
        """Execute batch insert for event_logs"""
        logger.info(f"Executing batch insert for {len(batch_data)} event_logs...")
        
        def batch_insert(cursor):
            execute_batch(cursor, """
                INSERT INTO event_logs (ticket_id, event_type, user_id, group_id, target_type, data) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, batch_data, page_size=100)
        
        try:
            self.db_operations.execute_db_operation(batch_insert, "Batch event_logs insert")
            logger.info(f"Successfully inserted {len(batch_data)} event_logs in batch")
        except Exception as e:
            logger.error(f"Failed to execute batch insert: {e}", exc_info=True)
            raise
    
    def add_to_event_logs_batch(self, data: Tuple):
        """Add data to event_logs batch queue"""
        with self.batch_lock:
            self.event_logs_batch.append(data)
            current_batch_size = len(self.event_logs_batch)
            
            # Process immediately if batch is full
            if current_batch_size >= config.batch.SIZE:
                logger.info(f"Batch is full ({current_batch_size} items), processing immediately...")
                batch_data = list(self.event_logs_batch)
                self._execute_batch_event_logs(batch_data)
                self.event_logs_batch.clear()


class MemoryManager:
    """Manages in-memory storage with automatic cleanup"""
    
    def __init__(self):
        self.prompt_response_in_memory: Dict[str, Dict] = {}
        self.memory_lock = threading.Lock()
    
    def get_or_create_ticket_data(self, ticket_id: str) -> Dict:
        """Get existing ticket data or create new entry"""
        with self.memory_lock:
            if ticket_id not in self.prompt_response_in_memory:
                self.prompt_response_in_memory[ticket_id] = {
                    "tokens": [],
                    "service_processing_last_update_time": None,
                    "created_at": time.time()
                }
            return self.prompt_response_in_memory[ticket_id]
    
    def update_ticket_data(self, ticket_id: str, **updates):
        """Update ticket data with thread safety"""
        with self.memory_lock:
            if ticket_id in self.prompt_response_in_memory:
                self.prompt_response_in_memory[ticket_id].update(updates)
    
    def remove_ticket_data(self, ticket_id: str):
        """Remove ticket data from memory"""
        with self.memory_lock:
            if ticket_id in self.prompt_response_in_memory:
                del self.prompt_response_in_memory[ticket_id]
    
    def cleanup_old_entries(self):
        """Clean up old memory entries to prevent memory leaks"""
        current_time = time.time()
        with self.memory_lock:
            keys_to_remove = [
                ticket_id for ticket_id, data in self.prompt_response_in_memory.items()
                if current_time - data.get('created_at', current_time) > config.memory.CLEANUP_AGE
            ]
            
            for key in keys_to_remove:
                del self.prompt_response_in_memory[key]
    
    def should_cleanup(self) -> bool:
        """Check if cleanup should be performed"""
        return len(self.prompt_response_in_memory) > config.memory.CLEANUP_THRESHOLD


class DatabaseOperations:
    """Handles core database operations with connection management"""
    
    def __init__(self, connection_pool: DatabaseConnectionPool):
        logger.info("Initializing DatabaseOperations...")
        self.connection_pool = connection_pool
    
    def execute_db_operation(self, operation_func, operation_name: str = "Database operation"):
        """
        Generic function to handle database operations with proper connection management.
        
        Args:
            operation_func: Function that takes a cursor and performs the database operation
            operation_name: Name of the operation for logging purposes
        """
        conn = self.connection_pool.get_connection()
        cursor = conn.cursor()
        try:
            operation_func(cursor)    
            conn.commit()         
            rows_affected = cursor.rowcount
            logger.debug(f"{operation_name} affected {rows_affected} rows")
        except Exception as e:
            logger.error(f"Database error in {operation_name}: {e}", exc_info=True)
            raise
        finally:
            cursor.close()
            self.connection_pool.release_connection(conn)


class DataSaver:
    """Main class for saving data with optimized performance"""
    
    def __init__(self):
        logger.info("Initializing DataSaver...")
>>>>>>> Stashed changes
        self.connection_pool = DatabaseConnectionPool()
        self.db_operations = DatabaseOperations(self.connection_pool)
        self.batch_processor = BatchProcessor(self.db_operations)
        self.memory_manager = MemoryManager()
<<<<<<< Updated upstream
=======
        logger.info("DataSaver initialized successfully")
>>>>>>> Stashed changes
    
    def save_data(self, headers: Dict[str, Any], data: Dict[str, Any]):
        """Main method to save data with batching and memory management"""
        ticket_id = headers.get('x-ticket-id')
        event_type = headers.get('event_type')
<<<<<<< Updated upstream
        
        # Validate required fields
        if not self._validate_required_fields(headers, data):
=======
                
        # Validate required fields
        if not self._validate_required_fields(headers, data):
            logger.error("Validation failed, aborting save_data operation")
>>>>>>> Stashed changes
            return
        
        if event_type == 'response':
            self._handle_response_event(headers, data, ticket_id)
        else:
            self._save_event_log(headers, data)
        
        # Periodically cleanup old memory entries
        if self.memory_manager.should_cleanup():
<<<<<<< Updated upstream
=======
            logger.info("Performing memory cleanup...")
>>>>>>> Stashed changes
            self.memory_manager.cleanup_old_entries()
    
    def _validate_required_fields(self, headers: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Validate that all required fields are present"""
        ticket_id = headers.get('x-ticket-id')
        event_type = headers.get('event_type')
        
        if not ticket_id:
            logger.error("Missing required field: x-ticket-id")
            return False
        
        if not event_type:
            logger.error("Missing required field: event_type")
            return False
        
        if event_type == 'response':
            status = data.get('status')
            if not status:
                logger.error("Missing required field: status for response event")
                return False
        
        return True
    
    def _handle_response_event(self, headers: Dict[str, Any], data: Dict[str, Any], ticket_id: str):
        """Handle response events with different statuses"""
        status = data.get('status')
<<<<<<< Updated upstream
=======
        
>>>>>>> Stashed changes
        ticket_data = self.memory_manager.get_or_create_ticket_data(ticket_id)
        
        if status == 'started':
            self._handle_started_status(headers, data, ticket_data)
        elif status == 'in_progress':
            self._handle_in_progress_status(data, ticket_data)
        elif status == 'completed':
            self._handle_completed_status(headers, data, ticket_id, ticket_data)
        else:
            logger.warning(f"Unknown status '{status}' for response event, saving as-is")
            self._save_event_log(headers, data)
    
    def _handle_started_status(self, headers: Dict[str, Any], data: Dict[str, Any], ticket_data: Dict):
        """Handle 'started' status for response events"""
        self.memory_manager.update_ticket_data(
            headers.get('x-ticket-id'),
            service_processing_last_update_time=data.get('service_processing_last_update_time'),
            tokens=[data.get('tokens')]
        )
        self._save_event_log(headers, data)
    
    def _handle_in_progress_status(self, data: Dict[str, Any], ticket_data: Dict):
        """Handle 'in_progress' status for response events"""
        self.memory_manager.update_ticket_data(
            data.get('ticket_id'),
            service_processing_last_update_time=data.get('service_processing_last_update_time'),
            tokens=ticket_data['tokens'] + [data.get('tokens')]
        )
        # Do not save the data record here, it will be saved when status is completed
    
    def _handle_completed_status(self, headers: Dict[str, Any], data: Dict[str, Any], ticket_id: str, ticket_data: Dict):
        """Handle 'completed' status for response events"""
        # Update with final token
        final_tokens = ticket_data['tokens'] + [data.get('tokens')]
<<<<<<< Updated upstream
=======
        
>>>>>>> Stashed changes
        self.memory_manager.update_ticket_data(
            ticket_id,
            service_processing_last_update_time=data.get('service_processing_last_update_time'),
            tokens=final_tokens
        )
        
        # Prepare final data
        final_data = data.copy()
        final_data['tokens'] = " ".join(final_tokens) if isinstance(final_tokens, list) else final_tokens
        final_data['service_processing_last_update_time'] = ticket_data['service_processing_last_update_time']
        
        # Save and cleanup
        self._save_event_log(headers, final_data)
        self.memory_manager.remove_ticket_data(ticket_id)
    
    def _save_event_log(self, headers: Dict[str, Any], data: Dict[str, Any]):
        """Save event log to batch queue"""
        event_log_data = (
            headers.get('x-ticket-id'),
            headers.get('event_type'),
            headers.get('user_id'),
            headers.get('group_id'),
            headers.get('target_type'),
            Json(data)
        )
<<<<<<< Updated upstream
=======
        logger.info(f"Event log data: {headers},  {data}")
>>>>>>> Stashed changes
        self.batch_processor.add_to_event_logs_batch(event_log_data)


# Utility function
def to_datetime(timestamp_in_ms: Optional[int]) -> Optional[datetime]:
    """Convert millisecond timestamp to datetime"""
    if timestamp_in_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_in_ms / 1000, tz=timezone.utc)

<<<<<<< Updated upstream

# Global instance for backward compatibility
data_saver = DataSaver()
save_data = data_saver.save_data
=======
>>>>>>> Stashed changes
