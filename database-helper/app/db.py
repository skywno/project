from psycopg2 import pool
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a connection pool
connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host="database",
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    port=os.getenv("POSTGRES_PORT")
)

def get_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)

def save_record(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Convert the data dictionary to hstore format
        hstore_data = ", ".join(f'{k} => "{v}"' for k, v in data.items())
        cursor.execute(
            "INSERT INTO logs (data) VALUES (%s::hstore)",
            (hstore_data,)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        release_connection(conn)