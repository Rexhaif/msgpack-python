#!/usr/bin/env python
"""
Intensive Asyncio GIL Release Benchmark for msgpack-python

This benchmark creates a more CPU-intensive scenario to better demonstrate
the GIL release benefit. It uses:
- More msgpack workers (to saturate threads)
- Larger payloads (to spend more time in GIL-released code)
- CPU-bound msgpack operations
"""
import asyncio
import time
import statistics
import msgpack
from typing import List, Dict


class LatencyTracker:
    """Tracks and reports latency statistics"""
    def __init__(self, name: str):
        self.name = name
        self.latencies: List[float] = []
    
    def record(self, latency_ms: float):
        self.latencies.append(latency_ms)
    
    def get_stats(self) -> Dict[str, float]:
        if not self.latencies:
            return {}
        sorted_lat = sorted(self.latencies)
        n = len(sorted_lat)
        return {
            'count': n,
            'mean': statistics.mean(self.latencies),
            'median': statistics.median(self.latencies),
            'p50': sorted_lat[n * 50 // 100],
            'p75': sorted_lat[n * 75 // 100],
            'p90': sorted_lat[n * 90 // 100],
            'p95': sorted_lat[n * 95 // 100],
            'p99': sorted_lat[n * 99 // 100],
            'min': min(self.latencies),
            'max': max(self.latencies),
        }
    
    def print_report(self):
        stats = self.get_stats()
        if not stats:
            print(f"{self.name}: No measurements")
            return
        
        print(f"\n  {self.name}:")
        print(f"    Samples:  {stats['count']:>6}")
        print(f"    Mean:     {stats['mean']:>6.3f} ms")
        print(f"    Median:   {stats['median']:>6.3f} ms")
        print(f"    P75:      {stats['p75']:>6.3f} ms")
        print(f"    P90:      {stats['p90']:>6.3f} ms")
        print(f"    P95:      {stats['p95']:>6.3f} ms")
        print(f"    P99:      {stats['p99']:>6.3f} ms")
        print(f"    Max:      {stats['max']:>6.3f} ms")


async def latency_monitor(tracker: LatencyTracker, duration_sec: float):
    """
    Monitors async operation latency by doing tiny sleeps.
    This simulates latency-sensitive async work (like handling requests).
    """
    end_time = asyncio.get_event_loop().time() + duration_sec
    
    while asyncio.get_event_loop().time() < end_time:
        start = time.perf_counter()
        await asyncio.sleep(0.001)  # Target: 1ms
        actual_latency_ms = (time.perf_counter() - start) * 1000
        tracker.record(actual_latency_ms)


async def intensive_msgpack_worker_large(duration_sec: float, stats: Dict):
    """
    Intensive msgpack worker with LARGE payloads (GIL released).
    Processes multiple large payloads per iteration.
    """
    # Large payload: 20KB (well above 1KB threshold)
    payload = b'x' * (20 * 1024)
    end_time = asyncio.get_event_loop().time() + duration_sec
    
    def heavy_msgpack_work():
        # Process multiple operations
        results = []
        for _ in range(5):  # 5 pack/unpack cycles per call
            packed = msgpack.packb(payload)
            unpacked = msgpack.unpackb(packed)
            results.append(len(unpacked))
        return sum(results)
    
    ops = 0
    while asyncio.get_event_loop().time() < end_time:
        await asyncio.to_thread(heavy_msgpack_work)
        ops += 5  # 5 operations per iteration
    
    stats['operations'] = stats.get('operations', 0) + ops


async def intensive_msgpack_worker_small(duration_sec: float, stats: Dict):
    """
    Intensive msgpack worker with SMALL payloads (GIL held).
    Processes multiple small payloads per iteration.
    """
    # Small payload: 256 bytes (below 1KB threshold)
    payload = b'x' * 256
    end_time = asyncio.get_event_loop().time() + duration_sec
    
    def heavy_msgpack_work():
        # Process multiple operations
        results = []
        for _ in range(5):  # 5 pack/unpack cycles per call
            packed = msgpack.packb(payload)
            unpacked = msgpack.unpackb(packed)
            results.append(len(unpacked))
        return sum(results)
    
    ops = 0
    while asyncio.get_event_loop().time() < end_time:
        await asyncio.to_thread(heavy_msgpack_work)
        ops += 5  # 5 operations per iteration
    
    stats['operations'] = stats.get('operations', 0) + ops


async def run_scenario(
    scenario_name: str,
    worker_func,
    num_workers: int,
    duration: float
):
    """Run a benchmark scenario"""
    print(f"\n{'='*70}")
    print(f"{scenario_name}")
    print(f"{'='*70}")
    print(f"  Workers: {num_workers}, Duration: {duration}s")
    
    tracker = LatencyTracker(f"Async Latency")
    stats = {}
    
    # Create all tasks
    tasks = [
        asyncio.create_task(latency_monitor(tracker, duration))
    ]
    
    for _ in range(num_workers):
        tasks.append(asyncio.create_task(
            worker_func(duration, stats)
        ))
    
    # Run and wait
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start
    
    # Report
    tracker.print_report()
    ops = stats.get('operations', 0)
    print(f"\n  Msgpack operations: {ops:,}")
    print(f"  Msgpack ops/sec:    {ops/elapsed:,.1f}")
    
    return tracker


async def main():
    """Main benchmark runner"""
    print("="*70)
    print("INTENSIVE ASYNCIO GIL BENCHMARK - msgpack-python")
    print("="*70)
    print("\nMeasures async operation latency under heavy msgpack load")
    print("\nTest scenarios:")
    print("  1. Baseline - No msgpack operations")
    print("  2. Small payloads (<1KB) - GIL held throughout")
    print("  3. Large payloads (>1KB) - GIL released during memcpy")
    
    DURATION = 10.0
    NUM_WORKERS = 8  # More workers = more contention
    
    # Baseline
    print(f"\n{'='*70}")
    print("BASELINE - No msgpack operations")
    print(f"{'='*70}")
    baseline_tracker = LatencyTracker("Async Latency")
    await latency_monitor(baseline_tracker, DURATION)
    baseline_tracker.print_report()
    
    # Small payloads (GIL held)
    small_tracker = await run_scenario(
        "SMALL PAYLOADS (<1KB) - GIL HELD",
        intensive_msgpack_worker_small,
        NUM_WORKERS,
        DURATION
    )
    
    # Large payloads (GIL released)
    large_tracker = await run_scenario(
        "LARGE PAYLOADS (>1KB) - GIL RELEASED",
        intensive_msgpack_worker_large,
        NUM_WORKERS,
        DURATION
    )
    
    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON - Latency Impact on Async Operations")
    print(f"{'='*70}")
    
    baseline_stats = baseline_tracker.get_stats()
    small_stats = small_tracker.get_stats()
    large_stats = large_tracker.get_stats()
    
    print(f"\n{'Metric':<10} {'Baseline':>10} {'Small/GIL':>12} {'Large/NoGIL':>12} {'Improvement':>12}")
    print("-" * 70)
    
    for metric in ['mean', 'p75', 'p90', 'p95', 'p99', 'max']:
        base_val = baseline_stats[metric]
        small_val = small_stats[metric]
        large_val = large_stats[metric]
        
        # Calculate overhead vs baseline
        small_overhead = small_val - base_val
        large_overhead = large_val - base_val
        
        # Improvement: reduction in overhead
        if small_overhead > 0:
            improvement_pct = ((small_overhead - large_overhead) / small_overhead) * 100
        else:
            improvement_pct = 0
        
        print(f"{metric.upper():<10} {base_val:>8.3f} ms "
              f"{small_val:>8.3f} ms (+{small_overhead:>4.2f}) "
              f"{large_val:>8.3f} ms (+{large_overhead:>4.2f}) "
              f"{improvement_pct:>8.1f}%")
    
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    small_mean_overhead = small_stats['mean'] - baseline_stats['mean']
    large_mean_overhead = large_stats['mean'] - baseline_stats['mean']
    mean_improvement = ((small_mean_overhead - large_mean_overhead) / small_mean_overhead * 100) if small_mean_overhead > 0 else 0
    
    small_p95_overhead = small_stats['p95'] - baseline_stats['p95']
    large_p95_overhead = large_stats['p95'] - baseline_stats['p95']
    p95_improvement = ((small_p95_overhead - large_p95_overhead) / small_p95_overhead * 100) if small_p95_overhead > 0 else 0
    
    print(f"""
GIL Release Impact Summary:

Mean latency overhead:
  - With GIL held (small):    +{small_mean_overhead:.3f} ms
  - With GIL released (large): +{large_mean_overhead:.3f} ms
  - Improvement:               {mean_improvement:.1f}%

P95 latency overhead:
  - With GIL held (small):    +{small_p95_overhead:.3f} ms
  - With GIL released (large): +{large_p95_overhead:.3f} ms
  - Improvement:               {p95_improvement:.1f}%

Interpretation:
  - Positive improvement % means GIL release REDUCES async latency overhead
  - This is beneficial for async applications running msgpack in threads
  - Lower tail latencies (P95, P99) are especially important for user-facing apps
""")


if __name__ == '__main__':
    asyncio.run(main())
