from psycopg2 import pool
from psycopg2.extras import Json
import os
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a connection pool
connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.getenv("POSTGRES_HOST"),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    port=os.getenv("POSTGRES_PORT")
)

def get_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)

def execute_db_operation(operation_func, operation_name="Database operation"):
    """
    Generic function to handle database operations with proper connection management.
    
    Args:
        operation_func: Function that takes a cursor and performs the database operation
        operation_name: Name of the operation for logging purposes
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        operation_func(cursor)
        conn.commit()
        logger.info(f"{operation_name} completed successfully")
        # Check how many rows were affected
        rows_affected = cursor.rowcount
        logger.info(f"UPDATE affected {rows_affected} rows")

    except Exception as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        release_connection(conn)


def save_request(headers: dict, data: dict):
    logger.info(f"Saving request: {data}")
    logger.info(f"Headers: {headers}")
    def insert_request(cursor):
        request_send_time = to_datetime(headers.get('client_request_send_time_in_ms'))
        ticket_id = data.get('ticket_id')
        user_id = data.get('user_id')
        group_id = data.get('group_id')
        target_type = data.get('target_type')
        
        # Insert the record into the logs table
        cursor.execute("""
            INSERT INTO logs (
                ticket_id, user_id, group_id, target_type, request_submission_time
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            ticket_id, user_id, group_id, target_type, request_send_time
        ))
    
    execute_db_operation(insert_request, "Request record save")

def save_response(headers: dict, data: dict):
    logger.info(f"Saving response: {data}")
    logger.info(f"Headers: {headers}")

    def insert_response(cursor):
        processing_start_time = to_datetime(headers.get('service_processing_start_time_in_ms'))
        processing_last_update_time = to_datetime(headers.get('service_processing_last_update_time_in_ms'))
        processing_end_time = to_datetime(headers.get('service_processing_end_time_in_ms'))
        ticket_id = data.get('ticket_id')
        status = data.get('status')
        message = data.get('message')

        # Update the logs table with the response
        cursor.execute("""
            UPDATE logs SET
                processing_start_time = %s,
                processing_last_update_time = %s,
                processing_end_time = %s,
                current_status = %s,
                message = %s
            WHERE ticket_id = %s
        """, (
            processing_start_time,
            processing_last_update_time,
            processing_end_time,
            status,
            message,
            ticket_id
        ))
    execute_db_operation(insert_response, "Response record save")

def save_queue_deleted(headers: dict):
    logger.info(f"Saving queue deleted: {headers}")

    def insert_queue_deleted(cursor):
        ticket_id = headers.get('name').split('.')[1]
        response_completion_time = to_datetime(headers.get('timestamp_in_ms'))
        
        cursor.execute("""
            UPDATE logs SET
                response_completion_time = %s
            WHERE ticket_id = %s
        """, (
            response_completion_time,
            ticket_id,
        ))
    
    execute_db_operation(insert_queue_deleted, "Queue deleted record save")

prompt_response_in_memory = {}

def save_data(headers: dict, data: dict):
    def insert_data(cursor):
        ticket_id = headers.get('x-ticket-id')
        event_type = headers.get('event_type')
        user_id = headers.get('user_id')
        group_id = headers.get('group_id')
        target_type = headers.get('target_type')
        cursor.execute("""
            INSERT INTO event_logs (ticket_id, event_type, user_id, group_id, target_type, data) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            ticket_id,
            event_type,
            user_id,
            group_id,
            target_type,
            Json(data)
        ))

    ticket_id = headers.get('x-ticket-id')
    event_type = headers.get('event_type')
    
    # Validate required fields
    if not ticket_id:
        logger.error("Missing required field: x-ticket-id")
        return
    
    if not event_type:
        logger.error("Missing required field: event_type")
        return

    if event_type == 'response':
        status = data.get('status')
        if not status:
            logger.error("Missing required field: status for response event")
            return
            
        # Initialize ticket data if it doesn't exist
        if ticket_id not in prompt_response_in_memory:
            prompt_response_in_memory[ticket_id] = {
                "tokens": [],
                "service_processing_last_update_time": None
            }
        
        if status == 'started':
            prompt_response_in_memory[ticket_id]['service_processing_last_update_time'] = data.get('service_processing_last_update_time')
            prompt_response_in_memory[ticket_id]['tokens'] = [data.get('tokens')]
        elif status == 'in_progress':
            prompt_response_in_memory[ticket_id]['service_processing_last_update_time'] = data.get('service_processing_last_update_time')
            prompt_response_in_memory[ticket_id]['tokens'].append(data.get('tokens'))
        elif status == 'completed':
            prompt_response_in_memory[ticket_id]['service_processing_last_update_time'] = data.get('service_processing_last_update_time')
            prompt_response_in_memory[ticket_id]['tokens'].append(data.get('tokens'))
            data['tokens'] = " ".join(prompt_response_in_memory[ticket_id]['tokens']) if type(prompt_response_in_memory[ticket_id]['tokens']) is list else prompt_response_in_memory[ticket_id]['tokens']
            data['service_processing_last_update_time'] = prompt_response_in_memory[ticket_id]['service_processing_last_update_time']
            execute_db_operation(insert_data, "Data record save")
            del prompt_response_in_memory[ticket_id]
        else:
            logger.warning(f"Unknown status '{status}' for response event, saving as-is")
            execute_db_operation(insert_data, "Data record save")
    else:
        execute_db_operation(insert_data, "Data record save")

# Could be its own util function
def to_datetime(timestamp_in_ms: int) -> datetime:
    if timestamp_in_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_in_ms / 1000, tz=timezone.utc)
