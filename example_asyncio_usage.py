#!/usr/bin/env python
"""
Example: Using msgpack with asyncio.to_thread()

This example demonstrates how to use msgpack in an asyncio application
with the GIL release benefits for large payloads.
"""
import asyncio
import os
import msgpack
import time


async def process_message_async(message_data: bytes) -> dict:
    """
    Process a msgpack message asynchronously.
    
    Uses asyncio.to_thread() to run msgpack.unpackb in a thread pool,
    which allows other async tasks to run concurrently.
    
    With large payloads (>1KB), the GIL is released during unpacking,
    allowing true parallelism across multiple concurrent calls.
    """
    # Offload CPU-bound msgpack unpacking to thread pool
    result = await asyncio.to_thread(msgpack.unpackb, message_data)
    return result


async def pack_message_async(data: dict) -> bytes:
    """
    Pack a dictionary to msgpack asynchronously.
    
    Uses asyncio.to_thread() to run msgpack.packb in a thread pool.
    """
    # Offload CPU-bound msgpack packing to thread pool
    result = await asyncio.to_thread(msgpack.packb, data)
    return result


async def handle_request(request_id: int, payload_size_kb: int):
    """
    Simulate handling a request with msgpack serialization.
    
    This represents a typical web server scenario where:
    1. Receive data (simulated)
    2. Pack it with msgpack
    3. Do some processing
    4. Unpack a response
    """
    print(f"Request {request_id}: Starting (payload: {payload_size_kb}KB)")
    
    # Create test data
    data = {
        'id': request_id,
        'payload': 'x' * int(payload_size_kb * 1024),
        'timestamp': time.time(),
    }
    
    # Pack the data (runs in thread pool with GIL released for large payloads)
    packed = await pack_message_async(data)
    
    # Simulate some async work
    await asyncio.sleep(0.01)
    
    # Unpack the data (runs in thread pool with GIL released for large payloads)
    unpacked = await process_message_async(packed)
    
    print(f"Request {request_id}: Completed")
    return unpacked


async def main():
    """
    Demonstrate concurrent request handling with msgpack.
    
    This shows how multiple requests can process msgpack data
    in parallel when using large payloads with GIL release.
    """
    print("="*70)
    print("EXAMPLE: Asyncio + msgpack with GIL Release")
    print("="*70)
    
    # Use CPU count for number of concurrent requests to avoid overloading
    num_requests = (os.cpu_count() or 4) * 2
    print(f"\n  System CPU cores detected: {os.cpu_count() or 4}")
    print(f"  Using {num_requests} concurrent requests (2x CPU cores)")
    
    # Scenario 1: Small payloads (GIL held - less parallelism)
    print(f"\nScenario 1: Small payloads (0.5 KB) - GIL held")
    print("-" * 70)
    start = time.perf_counter()
    
    tasks = [handle_request(i, 0.5) for i in range(num_requests)]
    results = await asyncio.gather(*tasks)
    
    elapsed = time.perf_counter() - start
    print(f"Processed {len(results)} requests in {elapsed:.3f}s")
    print(f"Throughput: {len(results)/elapsed:.1f} requests/sec")
    
    # Scenario 2: Large payloads (GIL released - more parallelism)
    print(f"\nScenario 2: Large payloads (10 KB) - GIL released")
    print("-" * 70)
    start = time.perf_counter()
    
    tasks = [handle_request(i, 10) for i in range(num_requests)]
    results = await asyncio.gather(*tasks)
    
    elapsed = time.perf_counter() - start
    print(f"Processed {len(results)} requests in {elapsed:.3f}s")
    print(f"Throughput: {len(results)/elapsed:.1f} requests/sec")
    
    print("\n" + "="*70)
    print("Explanation:")
    print("="*70)
    print("""
With large payloads (>1KB), msgpack releases the GIL during packing/unpacking.
This allows multiple asyncio.to_thread() calls to run in true parallel,
improving throughput for concurrent request handling.

Benefits:
- Better CPU utilization with multiple cores
- Lower latency for concurrent requests
- Event loop remains responsive during msgpack operations

Best practices:
- Use asyncio.to_thread() for CPU-bound msgpack operations
- Prefer large payloads when possible (>1KB) to benefit from GIL release
- Monitor thread pool size (default: min(32, CPU count + 4))
""")


if __name__ == '__main__':
    asyncio.run(main())
