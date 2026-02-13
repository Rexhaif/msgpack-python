#!/usr/bin/env python
"""
Multi-threaded Asyncio GIL Benchmark for msgpack-python

This benchmark demonstrates the GIL release benefit by showing:
1. Thread parallelism: Can multiple msgpack threads run simultaneously?
2. Async responsiveness: Do async tasks get starved by thread pool workers?

The key metric: With GIL released, multiple msgpack operations can run
in parallel, reducing total wall-clock time and async task starvation.
"""
import asyncio
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
    print("\nDemonstrates GIL release benefits:")
    print("  1. Thread parallelism (multiple threads make progress simultaneously)")
    print("  2. Async responsiveness (event loop not starved by threads)")
    print("\nKey metrics:")
    print("  - Parallelism ratio: How much parallel speedup (higher = better)")
    print("  - Async pings/sec: How responsive the event loop is (higher = better)")
    
    NUM_THREADS = 4
    ITERATIONS = 500
    
    # Test with small payloads (GIL held)
    small_results = await parallel_msgpack_benchmark(
        "SMALL PAYLOADS (256 bytes) - GIL HELD",
        msgpack_work_small,
        NUM_THREADS,
        ITERATIONS
    )
    
    # Test with large payloads (GIL released)
    large_results = await parallel_msgpack_benchmark(
        "LARGE PAYLOADS (50 KB) - GIL RELEASED",
        msgpack_work_large,
        NUM_THREADS,
        ITERATIONS
    )
    
    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON - GIL Release Benefits")
    print(f"{'='*70}")
    
    print(f"\n{'Metric':<30} {'Small/GIL':>15} {'Large/NoGIL':>15} {'Improvement':>12}")
    print("-" * 70)
    
    # Parallelism
    small_par = small_results['parallelism']
    large_par = large_results['parallelism']
    par_improvement = ((large_par - small_par) / small_par * 100) if small_par > 0 else 0
    print(f"{'Parallelism Ratio':<30} {small_par:>13.2f}x {large_par:>13.2f}x {par_improvement:>10.1f}%")
    
    # Operations throughput
    small_ops = small_results['ops_per_sec']
    large_ops = large_results['ops_per_sec']
    ops_improvement = ((large_ops - small_ops) / small_ops * 100) if small_ops > 0 else 0
    print(f"{'Operations/sec':<30} {small_ops:>13.1f} {large_ops:>13.1f} {ops_improvement:>10.1f}%")
    
    # Async responsiveness
    small_pings = small_results['ping_count'] / small_results['wall_time']
    large_pings = large_results['ping_count'] / large_results['wall_time']
    ping_improvement = ((large_pings - small_pings) / small_pings * 100) if small_pings > 0 else 0
    print(f"{'Async pings/sec':<30} {small_pings:>13.1f} {large_pings:>13.1f} {ping_improvement:>10.1f}%")
    
    # Latency
    small_lat = small_results['ping_avg_latency']
    large_lat = large_results['ping_avg_latency']
    lat_improvement = ((small_lat - large_lat) / small_lat * 100) if small_lat > 0 else 0
    print(f"{'Avg async latency (µs)':<30} {small_lat:>13.1f} {large_lat:>13.1f} {lat_improvement:>10.1f}%")
    
    small_p99 = small_results['ping_p99_latency']
    large_p99 = large_results['ping_p99_latency']
    p99_improvement = ((small_p99 - large_p99) / small_p99 * 100) if small_p99 > 0 else 0
    print(f"{'P99 async latency (µs)':<30} {small_p99:>13.1f} {large_p99:>13.1f} {p99_improvement:>10.1f}%")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"""
Parallelism Improvement: {par_improvement:+.1f}%
  - Small payloads: {small_par:.2f}x parallelism (GIL limits to ~1.0x)
  - Large payloads: {large_par:.2f}x parallelism (GIL released, closer to {NUM_THREADS}.0x ideal)
  
Async Responsiveness: {ping_improvement:+.1f}%
  - Higher pings/sec means the event loop can run more frequently
  - With GIL released, async tasks are less starved by thread pool

Conclusion:
  Positive improvements indicate GIL release is working and beneficial for:
  - Running multiple msgpack operations in parallel (thread pool)
  - Maintaining async responsiveness in asyncio applications
  - Reducing latency of async tasks running alongside msgpack threads
""")


if __name__ == '__main__':
    asyncio.run(main())
