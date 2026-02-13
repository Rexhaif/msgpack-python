#!/usr/bin/env python
"""
Asyncio GIL Release Benchmark for msgpack-python

This benchmark measures the extra latency introduced into non-msgpack related 
async code when running in parallel with msgpack operations in threads.

Comparison:
- Large payloads (>1KB): GIL is released during packing/unpacking
- Small payloads (<1KB): GIL is held (simulates original implementation)

The benchmark runs:
1. Background msgpack operations in asyncio.to_thread (threading)
2. Foreground async "ping" operations that measure latency
3. Compares latency with/without GIL release
"""
import asyncio
import os
import time
import statistics
import msgpack
from typing import List, Dict, Any


class LatencyMeasurement:
    """Tracks latency measurements"""
    def __init__(self, name: str):
        self.name = name
        self.latencies: List[float] = []
    
    def record(self, latency_ms: float):
        self.latencies.append(latency_ms)
    
    def stats(self) -> Dict[str, float]:
        if not self.latencies:
            return {}
        sorted_lat = sorted(self.latencies)
        return {
            'count': len(self.latencies),
            'mean': statistics.mean(self.latencies),
            'median': statistics.median(self.latencies),
            'p50': sorted_lat[len(sorted_lat) * 50 // 100],
            'p95': sorted_lat[len(sorted_lat) * 95 // 100],
            'p99': sorted_lat[len(sorted_lat) * 99 // 100],
            'min': min(self.latencies),
            'max': max(self.latencies),
        }
    
    def print_stats(self):
        stats = self.stats()
        if not stats:
            print(f"{self.name}: No data")
            return
        
        print(f"\n{self.name}:")
        print(f"  Count:  {stats['count']}")
        print(f"  Mean:   {stats['mean']:.3f} ms")
        print(f"  Median: {stats['median']:.3f} ms")
        print(f"  P50:    {stats['p50']:.3f} ms")
        print(f"  P95:    {stats['p95']:.3f} ms")
        print(f"  P99:    {stats['p99']:.3f} ms")
        print(f"  Min:    {stats['min']:.3f} ms")
        print(f"  Max:    {stats['max']:.3f} ms")


async def async_ping(measurement: LatencyMeasurement, duration_sec: float):
    """
    Continuously measures async operation latency.
    This represents non-msgpack async work that should not be blocked.
    """
    end_time = asyncio.get_event_loop().time() + duration_sec
    
    while asyncio.get_event_loop().time() < end_time:
        start = time.perf_counter()
        # Small async sleep to yield control
        await asyncio.sleep(0.001)  # 1ms target
        latency_ms = (time.perf_counter() - start) * 1000
        measurement.record(latency_ms)


async def msgpack_worker_large(duration_sec: float, ops_counter: List[int]):
    """
    Runs msgpack pack/unpack operations in threads with LARGE payloads.
    Large payloads (>1KB) trigger GIL release.
    """
    # Large payload > 1KB threshold (10KB)
    large_data = b'x' * (10 * 1024)
    end_time = asyncio.get_event_loop().time() + duration_sec
    
    def pack_unpack():
        packed = msgpack.packb(large_data)
        unpacked = msgpack.unpackb(packed)
        return unpacked
    
    count = 0
    while asyncio.get_event_loop().time() < end_time:
        # Run in thread pool (simulates real async usage)
        await asyncio.to_thread(pack_unpack)
        count += 1
    
    ops_counter[0] += count


async def msgpack_worker_small(duration_sec: float, ops_counter: List[int]):
    """
    Runs msgpack pack/unpack operations in threads with SMALL payloads.
    Small payloads (<1KB) keep GIL held (simulates original implementation).
    """
    # Small payload < 1KB threshold (500 bytes)
    small_data = b'x' * 500
    end_time = asyncio.get_event_loop().time() + duration_sec
    
    def pack_unpack():
        packed = msgpack.packb(small_data)
        unpacked = msgpack.unpackb(packed)
        return unpacked
    
    count = 0
    while asyncio.get_event_loop().time() < end_time:
        # Run in thread pool
        await asyncio.to_thread(pack_unpack)
        count += 1
    
    ops_counter[0] += count


async def run_benchmark(
    name: str,
    msgpack_worker_func,
    num_msgpack_workers: int = 4,
    duration_sec: float = 5.0
):
    """
    Run a benchmark scenario.
    
    Args:
        name: Benchmark name
        msgpack_worker_func: Worker function (large or small payload)
        num_msgpack_workers: Number of concurrent msgpack workers
        duration_sec: How long to run the benchmark
    """
    print(f"\n{'='*70}")
    print(f"Running: {name}")
    print(f"  Msgpack workers: {num_msgpack_workers}")
    print(f"  Duration: {duration_sec}s")
    print(f"{'='*70}")
    
    # Measurement for async ping latency
    ping_measurement = LatencyMeasurement(f"{name} - Async Ping Latency")
    
    # Counter for msgpack operations
    ops_counter = [0]
    
    # Create tasks
    tasks = []
    
    # Add ping task (measures latency of non-msgpack async ops)
    tasks.append(asyncio.create_task(
        async_ping(ping_measurement, duration_sec)
    ))
    
    # Add msgpack worker tasks
    for i in range(num_msgpack_workers):
        tasks.append(asyncio.create_task(
            msgpack_worker_func(duration_sec, ops_counter)
        ))
    
    # Run all tasks
    start_time = time.perf_counter()
    await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time
    
    # Print results
    ping_measurement.print_stats()
    print(f"\nMsgpack operations completed: {ops_counter[0]}")
    print(f"Msgpack ops/sec: {ops_counter[0] / total_time:.1f}")
    
    return ping_measurement


async def main():
    """Main benchmark function"""
    print("="*70)
    print("ASYNCIO GIL RELEASE BENCHMARK FOR MSGPACK-PYTHON")
    print("="*70)
    print("\nThis benchmark measures async operation latency when running")
    print("msgpack operations in parallel threads.")
    print("\nScenarios:")
    print("  1. BASELINE: No msgpack operations (reference)")
    print("  2. SMALL payloads (<1KB): GIL held (simulates original)")
    print("  3. LARGE payloads (>1KB): GIL released (new implementation)")
    
    duration = 5.0
    # Use actual CPU count to avoid overloading the system
    num_workers = os.cpu_count() or 4
    
    print(f"\n  System CPU cores detected: {num_workers}")
    print(f"  Using {num_workers} msgpack worker threads")
    
    # Baseline: No msgpack operations
    print("\n" + "="*70)
    print("SCENARIO 1: BASELINE (No msgpack operations)")
    print("="*70)
    baseline = LatencyMeasurement("Baseline - Async Ping Latency")
    ping_task = asyncio.create_task(async_ping(baseline, duration))
    await ping_task
    baseline.print_stats()
    
    # Small payloads: GIL held
    small_result = await run_benchmark(
        "SCENARIO 2: SMALL payloads (<1KB) - GIL HELD",
        msgpack_worker_small,
        num_msgpack_workers=num_workers,
        duration_sec=duration
    )
    
    # Large payloads: GIL released
    large_result = await run_benchmark(
        "SCENARIO 3: LARGE payloads (>1KB) - GIL RELEASED",
        msgpack_worker_large,
        num_msgpack_workers=num_workers,
        duration_sec=duration
    )
    
    # Summary comparison
    print("\n" + "="*70)
    print("SUMMARY COMPARISON")
    print("="*70)
    
    baseline_stats = baseline.stats()
    small_stats = small_result.stats()
    large_stats = large_result.stats()
    
    def calc_increase(baseline_val, test_val):
        if baseline_val == 0:
            return 0
        return ((test_val - baseline_val) / baseline_val) * 100
    
    print("\nLatency increases compared to baseline:")
    print(f"{'Metric':<15} {'Baseline':<12} {'Small (GIL)':<15} {'Large (NoGIL)':<15}")
    print("-" * 70)
    
    for metric in ['mean', 'p50', 'p95', 'p99']:
        baseline_val = baseline_stats[metric]
        small_val = small_stats[metric]
        large_val = large_stats[metric]
        
        small_inc = calc_increase(baseline_val, small_val)
        large_inc = calc_increase(baseline_val, large_val)
        
        print(f"{metric.upper():<15} {baseline_val:>9.3f} ms "
              f"{small_val:>9.3f} ms (+{small_inc:>5.1f}%) "
              f"{large_val:>9.3f} ms (+{large_inc:>5.1f}%)")
    
    print("\n" + "="*70)
    print("INTERPRETATION")
    print("="*70)
    print("""
The benchmark compares three scenarios:

1. BASELINE: Pure async operations without any msgpack work
2. SMALL payloads: Msgpack operations with GIL held (simulates original)
3. LARGE payloads: Msgpack operations with GIL released (new implementation)

Lower latency increase = Better async responsiveness

Expected results:
- SMALL payloads should show HIGHER latency increases (GIL contention)
- LARGE payloads should show LOWER latency increases (GIL released)

The difference shows the benefit of GIL release for async applications
running msgpack operations in background threads.
""")


if __name__ == '__main__':
    asyncio.run(main())
