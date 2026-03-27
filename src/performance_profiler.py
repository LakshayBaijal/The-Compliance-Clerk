"""
Performance profiling module for compliance document extraction.
Tracks and reports processing speed, bottlenecks, and optimization opportunities.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from functools import wraps
from collections import defaultdict
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger(__name__)


class PerformanceProfiler:
    """Track and analyze performance metrics."""
    
    def __init__(self):
        """Initialize profiler."""
        self.timings = defaultdict(list)  # {operation: [times]}
        self.counters = defaultdict(int)   # {operation: count}
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start profiling session."""
        self.start_time = time.time()
        self.timings.clear()
        self.counters.clear()
        logger.info("Performance profiling started")
    
    def end(self):
        """End profiling session."""
        self.end_time = time.time()
        logger.info(f"Performance profiling ended - Total time: {self.elapsed_time():.2f}s")
    
    def elapsed_time(self) -> float:
        """Get elapsed time since start."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time
    
    def record_timing(self, operation: str, duration: float):
        """
        Record timing for an operation.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
        """
        self.timings[operation].append(duration)
        self.counters[operation] += 1
    
    def record_counter(self, operation: str, count: int = 1):
        """
        Record counter for an operation.
        
        Args:
            operation: Operation name
            count: Count to add
        """
        self.counters[operation] += count
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get profiling summary.
        
        Returns:
            Dictionary with timing and counter statistics
        """
        summary = {
            "total_time_seconds": self.elapsed_time(),
            "operations": {}
        }
        
        for operation in set(list(self.timings.keys()) + list(self.counters.keys())):
            times = self.timings.get(operation, [])
            count = self.counters.get(operation, 0)
            
            if times:
                total_time = sum(times)
                avg_time = total_time / len(times)
                min_time = min(times)
                max_time = max(times)
                
                summary["operations"][operation] = {
                    "count": len(times),
                    "total_time": round(total_time, 3),
                    "average_time": round(avg_time, 3),
                    "min_time": round(min_time, 3),
                    "max_time": round(max_time, 3),
                    "percentage_of_total": round(
                        total_time / self.elapsed_time() * 100, 1
                    ) if self.elapsed_time() > 0 else 0
                }
            elif count > 0:
                summary["operations"][operation] = {
                    "count": count
                }
        
        # Sort by total time descending
        summary["operations"] = dict(sorted(
            summary["operations"].items(),
            key=lambda x: x[1].get("total_time", 0),
            reverse=True
        ))
        
        return summary
    
    def generate_report(self) -> str:
        """
        Generate human-readable performance report.
        
        Returns:
            Formatted performance report
        """
        summary = self.get_summary()
        
        lines = []
        lines.append("=" * 100)
        lines.append("PERFORMANCE PROFILING REPORT")
        lines.append("=" * 100)
        lines.append("")
        
        lines.append(f"Total Processing Time: {summary['total_time_seconds']:.2f} seconds")
        lines.append("")
        
        if summary["operations"]:
            lines.append("OPERATION TIMINGS (sorted by total time)")
            lines.append("-" * 100)
            lines.append(f"{'Operation':<30} {'Count':>8} {'Total (s)':>10} {'Avg (s)':>10} {'Min (s)':>10} {'Max (s)':>10} {'% Total':>8}")
            lines.append("-" * 100)
            
            for op, stats in summary["operations"].items():
                if "total_time" in stats:
                    lines.append(
                        f"{op:<30} {stats['count']:>8} "
                        f"{stats['total_time']:>10.3f} {stats['average_time']:>10.3f} "
                        f"{stats['min_time']:>10.3f} {stats['max_time']:>10.3f} "
                        f"{stats['percentage_of_total']:>7.1f}%"
                    )
                else:
                    lines.append(f"{op:<30} {stats['count']:>8} (counter)")
        
        lines.append("=" * 100)
        return "\n".join(lines)
    
    def save_report(self, output_dir: str = "output"):
        """
        Save performance report to file.
        
        Args:
            output_dir: Directory to save report
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        report_text = self.generate_report()
        report_file = output_path / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report_text)
        
        # Also save JSON for machine processing
        summary = self.get_summary()
        json_file = output_path / f"performance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_file.write_text(json.dumps(summary, indent=2))
        
        logger.info(f"Performance report saved: {report_file}")
        logger.info(f"Performance data saved: {json_file}")
        
        return report_file, json_file


# Global profiler instance
_profiler = PerformanceProfiler()


def measure_time(operation_name: str):
    """
    Decorator to measure function execution time.
    
    Args:
        operation_name: Name of the operation being measured
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                _profiler.record_timing(operation_name, duration)
                logger.debug(f"{operation_name} took {duration:.3f}s")
        
        return wrapper
    
    return decorator


def count_operation(operation_name: str, count: int = 1):
    """
    Count an operation.
    
    Args:
        operation_name: Name of the operation
        count: Count to add
    """
    _profiler.record_counter(operation_name, count)


def get_global_profiler() -> PerformanceProfiler:
    """Get global profiler instance."""
    return _profiler


# Example usage for testing
if __name__ == "__main__":
    profiler = PerformanceProfiler()
    profiler.start()
    
    # Simulate some operations
    profiler.record_timing("pdf_ingestion", 1.5)
    profiler.record_timing("pdf_ingestion", 1.3)
    profiler.record_timing("classification", 0.2)
    profiler.record_timing("classification", 0.19)
    profiler.record_timing("extraction", 0.8)
    profiler.record_timing("extraction", 0.75)
    profiler.record_timing("validation", 0.3)
    profiler.record_counter("pages_processed", 225)
    
    profiler.end()
    
    print(profiler.generate_report())
