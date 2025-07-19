import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class OperationMetrics:
    """Stores metrics for a single operation type"""
    
    def __init__(self, max_history: int = 1000):
        self.times: List[float] = []
        self.batch_sizes: List[int] = []
        self.error_count: int = 0
        self.max_history = max_history
    
    def add_operation(self, duration: float, batch_size: int = 1):
        """Add a new operation measurement"""
        self.times.append(duration)
        self.batch_sizes.append(batch_size)
        
        # Keep only recent history
        if len(self.times) > self.max_history:
            self.times.pop(0)
            self.batch_sizes.pop(0)
    
    def add_error(self):
        """Increment error count"""
        self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Calculate and return operation statistics"""
        if not self.times:
            return {}
        
        total_time = sum(self.times)
        total_operations = sum(self.batch_sizes)
        
        return {
            'count': len(self.times),
            'avg_duration_ms': round((total_time / len(self.times)) * 1000, 2),
            'min_duration_ms': round(min(self.times) * 1000, 2),
            'max_duration_ms': round(max(self.times) * 1000, 2),
            'avg_batch_size': round(total_operations / len(self.batch_sizes), 2),
            'total_operations': total_operations,
            'errors': self.error_count,
            'ops_per_second': round(total_operations / total_time, 2) if total_time > 0 else 0
        }


class PerformanceMonitor:
    """Monitors and tracks database operation performance"""
    
    def __init__(self, max_history: int = 1000):
        self.metrics: Dict[str, OperationMetrics] = defaultdict(lambda: OperationMetrics(max_history))
        self.lock = threading.Lock()
    
    def record_operation(self, operation_type: str, duration: float, batch_size: int = 1):
        """Record the duration of a database operation"""
        with self.lock:
            self.metrics[operation_type].add_operation(duration, batch_size)
    
    def record_error(self, operation_type: str):
        """Record an error for an operation type"""
        with self.lock:
            self.metrics[operation_type].add_error()
    
    def get_stats(self, operation_type: Optional[str] = None) -> Dict[str, Any]:
        """Get performance statistics"""
        with self.lock:
            if operation_type:
                return self.metrics[operation_type].get_stats()
            else:
                return {
                    op_type: metrics.get_stats() 
                    for op_type, metrics in self.metrics.items()
                }
    
    def log_performance_summary(self):
        """Log a comprehensive performance summary"""
        stats = self.get_stats()
        if not stats:
            logger.info("No performance data available yet")
            return
        
        logger.info("=== Performance Summary ===")
        for operation_type, operation_stats in stats.items():
            if operation_stats:  # Only log if we have stats
                logger.info(f"{operation_type}:")
                logger.info(f"  Operations: {operation_stats['count']}")
                logger.info(f"  Avg Duration: {operation_stats['avg_duration_ms']}ms")
                logger.info(f"  Avg Batch Size: {operation_stats['avg_batch_size']}")
                logger.info(f"  Total Records: {operation_stats['total_operations']}")
                logger.info(f"  Ops/Second: {operation_stats['ops_per_second']}")
                logger.info(f"  Errors: {operation_stats['errors']}")
        logger.info("==========================")
    
    def reset_stats(self, operation_type: Optional[str] = None):
        """Reset statistics for specific operation or all operations"""
        with self.lock:
            if operation_type:
                if operation_type in self.metrics:
                    self.metrics[operation_type] = OperationMetrics()
            else:
                self.metrics.clear()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def monitor_operation(operation_type: str):
    """Decorator to monitor database operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                performance_monitor.record_operation(operation_type, duration)
                return result
            except Exception as e:
                performance_monitor.record_error(operation_type)
                raise
        return wrapper
    return decorator


def monitor_batch_operation(operation_type: str, batch_size: int):
    """Decorator to monitor batch operations with their size"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                performance_monitor.record_operation(operation_type, duration, batch_size)
                return result
            except Exception as e:
                performance_monitor.record_error(operation_type)
                raise
        return wrapper
    return decorator 