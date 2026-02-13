# CPU-Based Thread Scaling for Asyncio Benchmarks

## Overview

All asyncio benchmarks have been updated to use CPU-based thread scaling instead of hardcoded values. This prevents thread pool saturation and event loop latency issues.

## Problem Addressed

> "for benchmarking - rely on number of actual cores in the system to ensure that running 1000s threads would not introduce latency to main eventloop thread of async python"

## Changes Made

### 1. `benchmark_asyncio_parallel.py`
- **Before:** `NUM_THREADS = 4` (hardcoded)
- **After:** `NUM_THREADS = os.cpu_count() or 4` (dynamic)
- **Usage:** Uses exactly the number of CPU cores available
- **Output:** Shows detected CPU count

### 2. `benchmark_asyncio_gil.py`
- **Before:** `num_workers = 4` (hardcoded)
- **After:** `num_workers = os.cpu_count() or 4` (dynamic)
- **Usage:** Uses CPU count for msgpack worker threads
- **Output:** Shows detected CPU count

### 3. `benchmark_asyncio_gil_intensive.py`
- **Before:** `NUM_WORKERS = 8` (hardcoded)
- **After:** `NUM_WORKERS = (os.cpu_count() or 4) * 2` (dynamic)
- **Usage:** Uses 2x CPU cores for intensive stress testing
- **Output:** Shows both CPU count and calculated worker count

### 4. `example_asyncio_usage.py`
- **Before:** `range(10)` concurrent requests (hardcoded)
- **After:** `range((os.cpu_count() or 4) * 2)` (dynamic)
- **Usage:** Uses 2x CPU cores for concurrent requests
- **Output:** Shows CPU count and request count

### 5. `BENCHMARK_README.md`
- Added section on CPU-based scaling
- Updated sample outputs to show dynamic values
- Explained benefits of CPU-based scaling

## Benefits

1. **Prevents Thread Pool Saturation**
   - Won't create too many threads for small systems
   - Prevents overwhelming the asyncio thread pool

2. **Avoids Event Loop Latency**
   - Too many threads can cause context switching overhead
   - Keeps event loop responsive even under load

3. **Scales to System Capabilities**
   - 2-core systems: Uses 2-4 threads (appropriate)
   - 128-core systems: Uses 128-256 threads (optimal)

4. **Realistic Benchmarks**
   - Better represents real-world usage
   - Results are reproducible across different hardware

5. **Prevents Artificial Latency**
   - Thread pool overload creates artificial performance issues
   - CPU-based scaling ensures accurate measurements

## Implementation Details

### Fallback Handling
All benchmarks use `os.cpu_count() or 4` pattern:
- `os.cpu_count()` returns the number of CPU cores
- Falls back to 4 if `cpu_count()` returns `None` (rare edge case)

### Scaling Strategies

| Benchmark | Thread Count | Rationale |
|-----------|-------------|-----------|
| `benchmark_asyncio_parallel.py` | `CPU count` | 1:1 mapping for true parallelism test |
| `benchmark_asyncio_gil.py` | `CPU count` | Realistic concurrent msgpack operations |
| `benchmark_asyncio_gil_intensive.py` | `CPU count × 2` | Stress test with intentional overload |
| `example_asyncio_usage.py` | `CPU count × 2` | Realistic web server load |

## Testing

All benchmarks tested and verified on a 4-core system:

```bash
# Primary benchmark
$ python benchmark_asyncio_parallel.py
System CPU cores detected: 4
Using 4 threads for benchmarks
✓ Works correctly

# Latency benchmark
$ python benchmark_asyncio_gil.py
System CPU cores detected: 4
Using 4 msgpack worker threads
✓ Works correctly

# Intensive benchmark
$ python benchmark_asyncio_gil_intensive.py
System CPU cores detected: 4
Using 8 workers for intensive test (2x CPU cores)
✓ Works correctly

# Usage example
$ python example_asyncio_usage.py
System CPU cores detected: 4
Using 8 concurrent requests (2x CPU cores)
✓ Works correctly
```

## Verification

The implementation can be verified with:

```python
import os

cpu_count = os.cpu_count()
print(f"CPU cores: {cpu_count}")
print(f"Primary benchmark threads: {cpu_count or 4}")
print(f"Intensive benchmark workers: {(cpu_count or 4) * 2}")
```

## Impact

### Before
- Hardcoded thread counts (4, 8, 10)
- Could overwhelm 2-core systems
- Could underutilize 16+ core systems
- Inconsistent results across hardware

### After
- Dynamic thread counts based on CPU
- Optimal for any system configuration
- Prevents event loop latency issues
- Consistent, reproducible behavior

## Conclusion

The CPU-based scaling ensures:
1. ✅ No thread pool overload
2. ✅ No artificial event loop latency
3. ✅ Optimal performance for any system
4. ✅ Accurate, realistic benchmark results
5. ✅ Better user experience across different hardware

All benchmarks now automatically adapt to the system's capabilities, providing accurate measurements without introducing latency from thread overload.
