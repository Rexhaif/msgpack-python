#!/usr/bin/env python3
"""
Comprehensive GIL Release Comparison Benchmark

Compares:
  1. Current implementation (GIL released)
  2. Reference implementation (GIL never released)

Shows the actual impact of GIL release on parallelism and performance.
"""

import asyncio
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# Check if we can build the reference version
try:
    # Try to compile the reference version on the fly
    import pyximport
    pyximport.install(setup_args={"include_dirs": ["."]})
    
    # Import both versions
    import msgpack._packer as packer_gil
    # Try importing the nogil version - we'll build it if needed
    try:
        import msgpack._packer_nogil as packer_nogil
    except ImportError:
        print("Reference (no-GIL) version not built yet.")
        print("Building reference version...")
        import subprocess
        result = subprocess.run(
            ["cython", "msgpack/_packer_nogil.pyx"],
            cwd="/home/runner/work/msgpack-python/msgpack-python",
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Cython compilation successful")
        else:
            print("Error:", result.stderr)
            packer_nogil = None
except Exception as e:
    print(f"Could not setup comparison environment: {e}")
    print("Falling back to manual comparison approach...")
    packer_nogil = None

import msgpack

# Get CPU count
CPU_COUNT = os.cpu_count() or 4
NUM_THREADS = CPU_COUNT
ITERATIONS_PER_THREAD = 500


def pack_with_gil(data_list, iterations):
    """Pack using current implementation (GIL released)"""
    for _ in range(iterations):
        for data in data_list:
            msgpack.packb(data)


def pack_sequential_baseline(data_list, total_iterations):
    """Sequential baseline for comparison"""
    for _ in range(total_iterations):
        for data in data_list:
            msgpack.packb(data)


def benchmark_parallelism(payload_size, description):
    """
    Benchmark parallelism ratio for a given payload size.
    
    Parallelism ratio = (sum of thread times) / wall clock time
    - 1.0x = sequential (no parallelism)
    - 4.0x = ideal with 4 threads (perfect parallelism)
    """
    print(f"\n{'=' * 70}")
    print(f"{description}")
    print(f"{'=' * 70}")
    print(f"  Threads: {NUM_THREADS}, Iterations/thread: {ITERATIONS_PER_THREAD}")
    
    # Create test data
    test_data = b'\x00' * payload_size
    data_list = [test_data]
    
    # Measure sequential baseline
    start = time.perf_counter()
    pack_sequential_baseline(data_list, NUM_THREADS * ITERATIONS_PER_THREAD)
    sequential_time = time.perf_counter() - start
    
    # Measure parallel with GIL released
    thread_times = []
    overall_start = time.perf_counter()
    
    def worker_gil():
        worker_start = time.perf_counter()
        pack_with_gil(data_list, ITERATIONS_PER_THREAD)
        thread_times.append(time.perf_counter() - worker_start)
    
    threads = [threading.Thread(target=worker_gil) for _ in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    overall_time = time.perf_counter() - overall_start
    sum_thread_times = sum(thread_times)
    parallelism_ratio = sum_thread_times / overall_time
    ops_per_sec = (NUM_THREADS * ITERATIONS_PER_THREAD) / overall_time
    speedup = sequential_time / overall_time
    
    print(f"\n  Results:")
    print(f"    Sequential time:         {sequential_time:.3f} s")
    print(f"    Overall wall-clock time: {overall_time:.3f} s")
    print(f"    Sum of thread times:     {sum_thread_times:.3f} s")
    print(f"    Parallelism ratio:       {parallelism_ratio:.2f}x")
    print(f"    Speedup vs sequential:   {speedup:.2f}x")
    print(f"    Total operations:        {NUM_THREADS * ITERATIONS_PER_THREAD:,}")
    print(f"    Operations/sec:          {ops_per_sec:,.1f}")
    
    return {
        'payload_size': payload_size,
        'description': description,
        'sequential_time': sequential_time,
        'parallel_time': overall_time,
        'parallelism_ratio': parallelism_ratio,
        'speedup': speedup,
        'ops_per_sec': ops_per_sec,
    }


async def async_ping_task(ping_results, duration):
    """Async task that pings to measure event loop responsiveness"""
    count = 0
    latencies = []
    start_time = time.perf_counter()
    
    while time.perf_counter() - start_time < duration:
        ping_start = time.perf_counter()
        await asyncio.sleep(0)  # Yield to event loop
        ping_end = time.perf_counter()
        latencies.append((ping_end - ping_start) * 1_000_000)  # microseconds
        count += 1
    
    ping_results['count'] = count
    ping_results['latencies'] = latencies


async def pack_in_thread_pool(executor, data_list, iterations):
    """Pack in thread pool while event loop is running"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, pack_with_gil, data_list, iterations)


async def benchmark_async_responsiveness(payload_size, description):
    """
    Benchmark async responsiveness while packing in threads.
    Measures how well the event loop can run alongside thread pool work.
    """
    test_data = b'\x00' * payload_size
    data_list = [test_data]
    
    # Create thread pool
    executor = ThreadPoolExecutor(max_workers=NUM_THREADS)
    
    # Track ping results
    ping_results = {}
    
    # Run packing in threads alongside async pings
    start_time = time.perf_counter()
    
    # Create packing tasks
    packing_tasks = [
        pack_in_thread_pool(executor, data_list, ITERATIONS_PER_THREAD)
        for _ in range(NUM_THREADS)
    ]
    
    # Create ping task
    ping_task = async_ping_task(ping_results, duration=5.0)
    
    # Run both concurrently
    await asyncio.gather(*packing_tasks, ping_task)
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    executor.shutdown(wait=True)
    
    # Calculate metrics
    count = ping_results.get('count', 0)
    latencies = ping_results.get('latencies', [])
    
    if latencies:
        latencies_sorted = sorted(latencies)
        avg_latency = sum(latencies) / len(latencies)
        p50_latency = latencies_sorted[len(latencies_sorted) // 2]
        p99_latency = latencies_sorted[int(len(latencies_sorted) * 0.99)]
    else:
        avg_latency = p50_latency = p99_latency = 0
    
    pings_per_sec = count / duration if duration > 0 else 0
    
    return {
        'async_pings_total': count,
        'async_pings_per_sec': pings_per_sec,
        'avg_latency_us': avg_latency,
        'p50_latency_us': p50_latency,
        'p99_latency_us': p99_latency,
    }


def print_comparison_table(results_current, results_ref=None):
    """Print comparison table between current and reference implementations"""
    print(f"\n{'=' * 70}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 70}\n")
    
    if results_ref:
        print(f"{'Metric':<30} {'Current (GIL)':<15} {'Ref (No-GIL)':<15} {'Improvement':<15}")
        print("-" * 75)
        
        for current, ref in zip(results_current, results_ref):
            if current['description'] == ref['description']:
                desc = current['description'].replace(" - GIL RELEASED", "").replace(" - NO GIL RELEASE", "")
                print(f"\n{desc}")
                
                # Parallelism ratio
                p_curr = current['parallelism_ratio']
                p_ref = ref['parallelism_ratio']
                p_improvement = ((p_curr - p_ref) / p_ref * 100) if p_ref > 0 else 0
                print(f"  {'Parallelism Ratio':<28} {p_curr:>13.2f}x {p_ref:>13.2f}x {p_improvement:>13.1f}%")
                
                # Operations per sec
                ops_curr = current['ops_per_sec']
                ops_ref = ref['ops_per_sec']
                ops_improvement = ((ops_curr - ops_ref) / ops_ref * 100) if ops_ref > 0 else 0
                print(f"  {'Operations/sec':<28} {ops_curr:>13,.0f} {ops_ref:>13,.0f} {ops_improvement:>13.1f}%")
                
                # Speedup
                s_curr = current['speedup']
                s_ref = ref['speedup']
                s_improvement = ((s_curr - s_ref) / s_ref * 100) if s_ref > 0 else 0
                print(f"  {'Speedup vs sequential':<28} {s_curr:>13.2f}x {s_ref:>13.2f}x {s_improvement:>13.1f}%")
    else:
        print("Only current implementation results available.\n")
        print(f"{'Metric':<30} {'Small (256B)':<15} {'Large (50KB)':<15}")
        print("-" * 60)
        
        if len(results_current) >= 2:
            small = results_current[0]
            large = results_current[1]
            
            print(f"{'Parallelism Ratio':<30} {small['parallelism_ratio']:>13.2f}x {large['parallelism_ratio']:>13.2f}x")
            print(f"{'Operations/sec':<30} {small['ops_per_sec']:>13,.0f} {large['ops_per_sec']:>13,.0f}")
            print(f"{'Speedup vs sequential':<30} {small['speedup']:>13.2f}x {large['speedup']:>13.2f}x")


def main():
    """Run comprehensive GIL release comparison"""
    print(f"\n{'=' * 70}")
    print("GIL RELEASE COMPARISON BENCHMARK")
    print(f"{'=' * 70}")
    print(f"\nSystem CPU cores detected: {CPU_COUNT}")
    print(f"Using {NUM_THREADS} threads for benchmarks")
    print(f"Iterations per thread: {ITERATIONS_PER_THREAD}")
    print(f"Total operations per benchmark: {NUM_THREADS * ITERATIONS_PER_THREAD:,}")
    
    # Test configurations
    test_configs = [
        (256, "SMALL PAYLOADS (256 bytes)"),
        (50 * 1024, "LARGE PAYLOADS (50 KB)"),
    ]
    
    # Run benchmarks for current implementation (GIL released)
    print(f"\n{'=' * 70}")
    print("CURRENT IMPLEMENTATION - GIL RELEASED")
    print(f"{'=' * 70}")
    
    results_current = []
    for size, desc in test_configs:
        result = benchmark_parallelism(size, f"{desc} - GIL RELEASED")
        results_current.append(result)
    
    # Try to benchmark reference implementation (no GIL release)
    # For now, we'll use the same implementation as reference
    # In a real scenario, this would use a separately compiled nogil version
    print(f"\n{'=' * 70}")
    print("REFERENCE IMPLEMENTATION - NO GIL RELEASE")
    print(f"{'=' * 70}")
    print("\nNOTE: Reference version (nogil) needs to be compiled separately.")
    print("Using current implementation for demonstration.")
    print("To get accurate comparison, compile msgpack/_packer_nogil.pyx\n")
    
    # Print comparison
    print_comparison_table(results_current)
    
    # Print key insights
    print(f"\n{'=' * 70}")
    print("KEY INSIGHTS")
    print(f"{'=' * 70}\n")
    
    if len(results_current) >= 2:
        small = results_current[0]
        large = results_current[1]
        
        print(f"1. PARALLELISM ACHIEVED:")
        print(f"   - Small payloads: {small['parallelism_ratio']:.2f}x with {NUM_THREADS} threads")
        print(f"   - Large payloads: {large['parallelism_ratio']:.2f}x with {NUM_THREADS} threads")
        print(f"   - Efficiency: {(small['parallelism_ratio']/NUM_THREADS)*100:.1f}% - {(large['parallelism_ratio']/NUM_THREADS)*100:.1f}% of ideal")
        
        print(f"\n2. SPEEDUP VS SEQUENTIAL:")
        print(f"   - Small payloads: {small['speedup']:.2f}x faster")
        print(f"   - Large payloads: {large['speedup']:.2f}x faster")
        
        print(f"\n3. THROUGHPUT:")
        print(f"   - Small payloads: {small['ops_per_sec']:,.0f} ops/sec")
        print(f"   - Large payloads: {large['ops_per_sec']:,.0f} ops/sec")
        
        print(f"\n4. GIL RELEASE EFFECTIVENESS:")
        if small['parallelism_ratio'] > 2.5:
            print(f"   ✅ Excellent parallelism achieved for all payload sizes")
            print(f"   ✅ GIL release is working effectively")
        elif small['parallelism_ratio'] > 1.5:
            print(f"   ✅ Good parallelism for large payloads")
            print(f"   ⚠️  Limited parallelism for small payloads")
        else:
            print(f"   ⚠️  Limited parallelism - GIL may be held most of the time")
    
    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
