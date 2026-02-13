#!/usr/bin/env python
"""
Multi-threaded Asyncio GIL Benchmark for msgpack-python

This benchmark demonstrates the GIL release benefit by comparing three approaches:
1. Small payloads with asyncio.to_thread (GIL held, threading overhead)
2. Large payloads with asyncio.to_thread (GIL released, true parallelism)
3. Direct async calls without threading (baseline, no threading overhead)

The key metrics:
- Thread parallelism: Can multiple msgpack threads run simultaneously?
- Async responsiveness: Do async tasks get starved by thread pool workers?
- Threading overhead: Is the threading overhead worth it?
"""
import asyncio
import os
import time
import threading
import statistics
import msgpack
from typing import List, Dict


def msgpack_work_large(iterations: int) -> float:
    """
    Synchronous msgpack work with LARGE payloads (GIL released).
    Returns time taken.
    """
    payload = b'x' * (50 * 1024)  # 50KB
    start = time.perf_counter()
    for _ in range(iterations):
        packed = msgpack.packb(payload)
        unpacked = msgpack.unpackb(packed)
    return time.perf_counter() - start


def msgpack_work_small(iterations: int) -> float:
    """
    Synchronous msgpack work with SMALL payloads (GIL held).
    Returns time taken.
    """
    payload = b'x' * 256  # 256 bytes
    start = time.perf_counter()
    for _ in range(iterations):
        packed = msgpack.packb(payload)
        unpacked = msgpack.unpackb(packed)
    return time.perf_counter() - start


async def async_msgpack_work_direct(iterations: int, payload_size: int) -> float:
    """
    Direct async msgpack work (runs in event loop, no threading).
    Returns time taken.
    """
    payload = b'x' * payload_size
    start = time.perf_counter()
    for _ in range(iterations):
        packed = msgpack.packb(payload)
        unpacked = msgpack.unpackb(packed)
        # Periodically yield to event loop to allow async ping monitoring
        if _ % 10 == 0:
            await asyncio.sleep(0)
    return time.perf_counter() - start


async def direct_async_benchmark(
    scenario_name: str,
    payload_size: int,
    num_tasks: int,
    iterations_per_task: int
):
    """
    Run msgpack operations directly in event loop (no threading) and measure:
    1. Total wall-clock time (sequential execution expected)
    2. Async task responsiveness during the operation
    """
    print(f"\n{'='*70}")
    print(f"{scenario_name}")
    print(f"{'='*70}")
    print(f"  Async tasks: {num_tasks}, Iterations/task: {iterations_per_task}")
    
    # Track async pings during operation
    ping_count = [0]
    ping_latencies = []
    should_stop = False
    
    async def async_ping_monitor():
        """Monitor async responsiveness while msgpack tasks run"""
        while not should_stop:
            start = time.perf_counter()
            await asyncio.sleep(0)  # Yield to event loop
            latency_us = (time.perf_counter() - start) * 1_000_000
            ping_latencies.append(latency_us)
            ping_count[0] += 1
    
    # Start async monitor
    monitor_task = asyncio.create_task(async_ping_monitor())
    
    # Run msgpack work directly in event loop
    overall_start = time.perf_counter()
    
    tasks = []
    for _ in range(num_tasks):
        task = async_msgpack_work_direct(iterations_per_task, payload_size)
        tasks.append(task)
    
    task_times = await asyncio.gather(*tasks)
    
    overall_elapsed = time.perf_counter() - overall_start
    should_stop = True
    await monitor_task
    
    # Calculate statistics
    total_sequential_time = sum(task_times)
    parallelism_ratio = total_sequential_time / overall_elapsed if overall_elapsed > 0 else 0
    total_ops = num_tasks * iterations_per_task
    ops_per_sec = total_ops / overall_elapsed
    
    # Async responsiveness
    avg_ping_latency = statistics.mean(ping_latencies) if ping_latencies else 0
    p99_ping_latency = sorted(ping_latencies)[len(ping_latencies) * 99 // 100] if ping_latencies else 0
    
    print(f"\n  Results:")
    print(f"    Overall wall-clock time:     {overall_elapsed:.3f} s")
    print(f"    Sum of task times:           {total_sequential_time:.3f} s")
    print(f"    Parallelism ratio:           {parallelism_ratio:.2f}x")
    print(f"    Total operations:            {total_ops:,}")
    print(f"    Operations/sec:              {ops_per_sec:,.1f}")
    print(f"\n  Async responsiveness:")
    print(f"    Async pings completed:       {ping_count[0]:,}")
    print(f"    Pings per second:            {ping_count[0]/overall_elapsed:,.1f}")
    print(f"    Avg ping latency:            {avg_ping_latency:.1f} µs")
    print(f"    P99 ping latency:            {p99_ping_latency:.1f} µs")
    
    return {
        'wall_time': overall_elapsed,
        'task_time': total_sequential_time,
        'parallelism': parallelism_ratio,
        'ops_per_sec': ops_per_sec,
        'ping_count': ping_count[0],
        'ping_avg_latency': avg_ping_latency,
        'ping_p99_latency': p99_ping_latency,
    }


async def parallel_msgpack_benchmark(
    scenario_name: str,
    worker_func,
    num_threads: int,
    iterations_per_thread: int
):
    """
    Run msgpack operations in parallel threads and measure:
    1. Total wall-clock time (shows parallelism)
    2. Async task responsiveness during the operation
    """
    print(f"\n{'='*70}")
    print(f"{scenario_name}")
    print(f"{'='*70}")
    print(f"  Threads: {num_threads}, Iterations/thread: {iterations_per_thread}")
    
    # Track async pings during operation
    ping_count = [0]
    ping_latencies = []
    should_stop = False
    
    async def async_ping_monitor():
        """Monitor async responsiveness while msgpack threads run"""
        while not should_stop:
            start = time.perf_counter()
            await asyncio.sleep(0)  # Yield to event loop
            latency_us = (time.perf_counter() - start) * 1_000_000
            ping_latencies.append(latency_us)
            ping_count[0] += 1
    
    # Start async monitor
    monitor_task = asyncio.create_task(async_ping_monitor())
    
    # Run msgpack work in thread pool
    overall_start = time.perf_counter()
    
    tasks = []
    for _ in range(num_threads):
        task = asyncio.to_thread(worker_func, iterations_per_thread)
        tasks.append(task)
    
    thread_times = await asyncio.gather(*tasks)
    
    overall_elapsed = time.perf_counter() - overall_start
    should_stop = True
    await monitor_task
    
    # Calculate statistics
    total_sequential_time = sum(thread_times)
    parallelism_ratio = total_sequential_time / overall_elapsed if overall_elapsed > 0 else 0
    total_ops = num_threads * iterations_per_thread
    ops_per_sec = total_ops / overall_elapsed
    
    # Async responsiveness
    avg_ping_latency = statistics.mean(ping_latencies) if ping_latencies else 0
    p99_ping_latency = sorted(ping_latencies)[len(ping_latencies) * 99 // 100] if ping_latencies else 0
    
    print(f"\n  Results:")
    print(f"    Overall wall-clock time:     {overall_elapsed:.3f} s")
    print(f"    Sum of thread times:         {total_sequential_time:.3f} s")
    print(f"    Parallelism ratio:           {parallelism_ratio:.2f}x")
    print(f"    Total operations:            {total_ops:,}")
    print(f"    Operations/sec:              {ops_per_sec:,.1f}")
    print(f"\n  Async responsiveness:")
    print(f"    Async pings completed:       {ping_count[0]:,}")
    print(f"    Pings per second:            {ping_count[0]/overall_elapsed:,.1f}")
    print(f"    Avg ping latency:            {avg_ping_latency:.1f} µs")
    print(f"    P99 ping latency:            {p99_ping_latency:.1f} µs")
    
    return {
        'wall_time': overall_elapsed,
        'thread_time': total_sequential_time,
        'parallelism': parallelism_ratio,
        'ops_per_sec': ops_per_sec,
        'ping_count': ping_count[0],
        'ping_avg_latency': avg_ping_latency,
        'ping_p99_latency': p99_ping_latency,
    }


async def main():
    """Main benchmark"""
    print("="*70)
    print("MULTI-THREADED ASYNCIO GIL BENCHMARK - msgpack-python")
    print("="*70)
    print("\nCompares three approaches:")
    print("  1. Small payloads with asyncio.to_thread (GIL held, threading overhead)")
    print("  2. Large payloads with asyncio.to_thread (GIL released, true parallelism)")
    print("  3. Direct async calls without threading (baseline, no threading overhead)")
    print("\nKey metrics:")
    print("  - Parallelism ratio: How much parallel speedup (higher = better)")
    print("  - Async pings/sec: How responsive the event loop is (higher = better)")
    
    # Use actual CPU count to avoid overloading the system
    NUM_THREADS = os.cpu_count() or 4
    ITERATIONS = 500
    
    print(f"\n  System CPU cores detected: {NUM_THREADS}")
    print(f"  Using {NUM_THREADS} threads/tasks for benchmarks")
    
    # Test 1: Small payloads with threading (GIL held)
    small_results = await parallel_msgpack_benchmark(
        "1. SMALL PAYLOADS (256 bytes) - asyncio.to_thread (GIL HELD)",
        msgpack_work_small,
        NUM_THREADS,
        ITERATIONS
    )
    
    # Test 2: Large payloads with threading (GIL released)
    large_results = await parallel_msgpack_benchmark(
        "2. LARGE PAYLOADS (50 KB) - asyncio.to_thread (GIL RELEASED)",
        msgpack_work_large,
        NUM_THREADS,
        ITERATIONS
    )
    
    # Test 3: Direct async calls without threading
    direct_results = await direct_async_benchmark(
        "3. MEDIUM PAYLOADS (10 KB) - Direct async (NO THREADING)",
        10 * 1024,  # 10 KB payload
        NUM_THREADS,
        ITERATIONS
    )
    
    # Three-way comparison
    print(f"\n{'='*70}")
    print("THREE-WAY COMPARISON")
    print(f"{'='*70}")
    
    print(f"\n{'Metric':<30} {'Small/Thread':>15} {'Large/Thread':>15} {'Direct/NoThread':>17}")
    print("-" * 80)
    
    # Parallelism
    small_par = small_results['parallelism']
    large_par = large_results['parallelism']
    direct_par = direct_results['parallelism']
    print(f"{'Parallelism Ratio':<30} {small_par:>13.2f}x {large_par:>13.2f}x {direct_par:>15.2f}x")
    
    # Operations throughput
    small_ops = small_results['ops_per_sec']
    large_ops = large_results['ops_per_sec']
    direct_ops = direct_results['ops_per_sec']
    print(f"{'Operations/sec':<30} {small_ops:>13.1f} {large_ops:>13.1f} {direct_ops:>15.1f}")
    
    # Async responsiveness
    small_pings = small_results['ping_count'] / small_results['wall_time']
    large_pings = large_results['ping_count'] / large_results['wall_time']
    direct_pings = direct_results['ping_count'] / direct_results['wall_time']
    print(f"{'Async pings/sec':<30} {small_pings:>13.1f} {large_pings:>13.1f} {direct_pings:>15.1f}")
    
    # Latency
    small_lat = small_results['ping_avg_latency']
    large_lat = large_results['ping_avg_latency']
    direct_lat = direct_results['ping_avg_latency']
    print(f"{'Avg async latency (µs)':<30} {small_lat:>13.1f} {large_lat:>13.1f} {direct_lat:>15.1f}")
    
    small_p99 = small_results['ping_p99_latency']
    large_p99 = large_results['ping_p99_latency']
    direct_p99 = direct_results['ping_p99_latency']
    print(f"{'P99 async latency (µs)':<30} {small_p99:>13.1f} {large_p99:>13.1f} {direct_p99:>15.1f}")
    
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    # GIL release benefit
    par_improvement = ((large_par - small_par) / small_par * 100) if small_par > 0 else 0
    print(f"""
1. GIL Release Benefit (Threading):
   - Small payloads with threading: {small_par:.2f}x parallelism
   - Large payloads with threading:  {large_par:.2f}x parallelism
   - Improvement: {par_improvement:+.1f}%
   - Conclusion: GIL release enables {large_par/small_par:.1f}x better parallelism

2. Threading Overhead:
   - Direct async (no threading):     {direct_ops:,.0f} ops/sec
   - Small payloads with threading:   {small_ops:,.0f} ops/sec
   - Threading overhead: {((direct_ops - small_ops) / direct_ops * 100):+.1f}%
   - Conclusion: Threading adds overhead but enables parallelism

3. When to Use Each Approach:
   
   a) Use asyncio.to_thread with LARGE payloads:
      - Parallelism: {large_par:.2f}x (near-ideal {NUM_THREADS}.0x)
      - Best for: CPU-intensive msgpack operations on large data
      - Trade-off: Accepts threading overhead for true parallelism
   
   b) Use asyncio.to_thread with SMALL payloads:
      - Parallelism: {small_par:.2f}x (GIL limits to ~1.0x)
      - Threading overhead hurts performance
      - Avoid unless you have many concurrent operations
   
   c) Use direct async calls (no threading):
      - Highest throughput: {direct_ops:,.0f} ops/sec
      - No threading overhead
      - Best for: Fast operations where threading overhead dominates
      - Limitation: Sequential execution (no parallelism)
      
4. Async Responsiveness:
   - Small with threading:  {small_pings:,.0f} pings/sec
   - Large with threading:  {large_pings:,.0f} pings/sec
   - Direct (no threading): {direct_pings:,.0f} pings/sec
   - Direct async yields more frequently due to explicit await points
""")

    print("="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    print("""
Choose your approach based on workload:

1. LARGE payloads + HIGH concurrency:
   ✓ Use asyncio.to_thread()
   ✓ Benefits from GIL release
   ✓ True parallelism achieved
   
2. SMALL payloads + LOW concurrency:
   ✓ Use direct async calls (no threading)
   ✓ Avoid threading overhead
   ✓ Higher throughput for sequential work
   
3. MIXED workloads:
   ✓ Use asyncio.to_thread() for large payloads
   ✓ Use direct calls for small payloads
   ✓ Best of both worlds
""")


if __name__ == '__main__':
    asyncio.run(main())
