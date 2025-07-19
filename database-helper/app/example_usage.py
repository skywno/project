"""
Example usage of the refactored database helper

This script demonstrates how to use the cleaner, more organized database API
with performance monitoring and configuration management.
"""

import json
import time
from app.db import DataSaver, to_datetime
from app.performance_monitor import performance_monitor
from app.config import config


def example_basic_usage():
    """Example of basic data saving"""
    print("=== Basic Usage Example ===")
    
    # Create a data saver instance
    data_saver = DataSaver()
    
    # Example headers and data
    headers = {
        'x-ticket-id': 'ticket_123',
        'event_type': 'request',
        'user_id': 'user_456',
        'group_id': 'group_789',
        'target_type': 'chat'
    }
    
    data = {
        'message': 'Hello, world!',
        'timestamp': time.time()
    }
    
    # Save the data
    data_saver.save_data(headers, data)
    print("Data saved successfully!")


def example_response_streaming():
    """Example of handling streaming response events"""
    print("\n=== Response Streaming Example ===")
    
    data_saver = DataSaver()
    ticket_id = 'streaming_ticket_123'
    
    # Simulate a streaming response
    headers = {
        'x-ticket-id': ticket_id,
        'event_type': 'response',
        'user_id': 'user_456',
        'group_id': 'group_789',
        'target_type': 'chat'
    }
    
    # Started status
    started_data = {
        'status': 'started',
        'tokens': 'Hello',
        'service_processing_last_update_time': time.time()
    }
    data_saver.save_data(headers, started_data)
    print("Started event saved")
    
    # In progress status (multiple chunks)
    for i in range(3):
        in_progress_data = {
            'status': 'in_progress',
            'tokens': f' chunk_{i+1}',
            'service_processing_last_update_time': time.time()
        }
        data_saver.save_data(headers, in_progress_data)
        print(f"In progress chunk {i+1} saved")
        time.sleep(0.1)  # Simulate processing time
    
    # Completed status
    completed_data = {
        'status': 'completed',
        'tokens': ' world!',
        'service_processing_last_update_time': time.time()
    }
    data_saver.save_data(headers, completed_data)
    print("Completed event saved")


def example_performance_monitoring():
    """Example of using performance monitoring"""
    print("\n=== Performance Monitoring Example ===")
    
    data_saver = DataSaver()
    
    # Generate some load
    for i in range(50):
        headers = {
            'x-ticket-id': f'perf_test_{i}',
            'event_type': 'test',
            'user_id': 'user_456',
            'group_id': 'group_789',
            'target_type': 'test'
        }
        
        data = {
            'test_data': f'data_{i}',
            'timestamp': time.time()
        }
        
        data_saver.save_data(headers, data)
    
    # Wait for batch processing
    time.sleep(2)
    
    # Show performance stats
    print("Performance Statistics:")
    performance_monitor.log_performance_summary()


def example_configuration():
    """Example of configuration management"""
    print("\n=== Configuration Example ===")
    
    print("Current Configuration:")
    config_dict = config.to_dict()
    for section, settings in config_dict.items():
        print(f"\n{section.upper()}:")
        for key, value in settings.items():
            print(f"  {key}: {value}")


def example_utility_functions():
    """Example of utility functions"""
    print("\n=== Utility Functions Example ===")
    
    # Convert timestamp
    timestamp_ms = int(time.time() * 1000)
    dt = to_datetime(timestamp_ms)
    print(f"Timestamp {timestamp_ms} -> {dt}")
    
    # Handle None timestamp
    dt_none = to_datetime(None)
    print(f"None timestamp -> {dt_none}")


def main():
    """Run all examples"""
    print("Database Helper - Refactored API Examples")
    print("=" * 50)
    
    try:
        example_basic_usage()
        example_response_streaming()
        example_performance_monitoring()
        example_configuration()
        example_utility_functions()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        print("Make sure your database is running and properly configured.")


if __name__ == "__main__":
    main() 