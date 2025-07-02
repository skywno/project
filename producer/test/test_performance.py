#!/usr/bin/env python3
"""
Performance test script for the /task endpoint
"""
import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict

async def test_endpoint(session: aiohttp.ClientSession, url: str, endpoint: str) -> Dict:
    """Test a single endpoint request."""
    start_time = time.time()
    try:
        if endpoint == "/":
            async with session.get(url) as response:
                await response.text()
        else:
            async with session.post(url) as response:
                await response.text()
        
        duration = time.time() - start_time
        return {"success": True, "duration": duration, "status": response.status}
    except Exception as e:
        duration = time.time() - start_time
        return {"success": False, "duration": duration, "error": str(e)}

async def run_load_test(base_url: str, endpoint: str, num_requests: int, concurrency: int):
    """Run a load test with specified concurrency."""
    print(f"\nTesting {endpoint} endpoint:")
    print(f"Total requests: {num_requests}")
    print(f"Concurrency: {concurrency}")
    
    async with aiohttp.ClientSession() as session:
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_request():
            async with semaphore:
                return await test_endpoint(session, f"{base_url}{endpoint}", endpoint)
        
        # Create all tasks
        tasks = [limited_request() for _ in range(num_requests)]
        
        # Run all tasks
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Process results
        successful_requests = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_requests = [r for r in results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        if successful_requests:
            durations = [r["duration"] for r in successful_requests]
            avg_duration = statistics.mean(durations)
            median_duration = statistics.median(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            
            requests_per_second = len(successful_requests) / total_time
            
            print(f"\nResults:")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Successful requests: {len(successful_requests)}")
            print(f"  Failed requests: {len(failed_requests)}")
            print(f"  Exceptions: {len(exceptions)}")
            print(f"  Requests per second: {requests_per_second:.2f}")
            print(f"  Average response time: {avg_duration*1000:.2f}ms")
            print(f"  Median response time: {median_duration*1000:.2f}ms")
            print(f"  Min response time: {min_duration*1000:.2f}ms")
            print(f"  Max response time: {max_duration*1000:.2f}ms")
        else:
            print("No successful requests!")

async def main():
    """Main test function."""
    base_url = "http://localhost:8000"  # Adjust if your server runs on different port
    
    print("Performance Test for FastAPI Endpoints")
    print("=" * 50)
    
    # Test the simple endpoint first
    await run_load_test(base_url, "/", num_requests=1000, concurrency=100)
    
    # Test the task endpoint with different concurrency levels
    concurrency_levels = [10, 20, 50, 100]
    
    for concurrency in concurrency_levels:
        await run_load_test(base_url, "/task", num_requests=100, concurrency=concurrency)
        await asyncio.sleep(2)  # Brief pause between tests

if __name__ == "__main__":
    asyncio.run(main()) 