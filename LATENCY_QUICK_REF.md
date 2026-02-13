# Latency Quick Reference

## TL;DR: Should I Use GIL Release?

### 🚀 YES - Use Large Payloads (>1KB, GIL Released)
- ✅ Batch processing / ETL pipelines
- ✅ High-throughput web servers
- ✅ Background workers
- ✅ Data processing jobs
- ✅ P99 latency budget: >50ms

### ⚠️ NO - Use Small Payloads (<1KB, GIL Held)
- ❌ Real-time applications
- ❌ Interactive/gaming systems
- ❌ Financial trading
- ❌ Chat applications
- ❌ P99 latency budget: <10ms

### 🤔 MAYBE - Evaluate Based on Requirements
- 🔍 Mixed workloads: Use hybrid approach
- 🔍 P99 latency budget: 10-50ms
- 🔍 Moderate throughput needs
- 🔍 Profile in production first

## The Trade-off at a Glance

```
GIL Release (Large Payloads >1KB)
  ✅ Pros: +140% parallelism, better throughput
  ❌ Cons: 2-3x higher P99 latency

GIL Held (Small Payloads <1KB)
  ✅ Pros: Lower P99 latency, consistent
  ❌ Cons: No parallelism, slower throughput
```

## Quick Decision Tree

```
Is your application latency-sensitive?
│
├─ NO  → Use large payloads (>1KB)
│        Benefit from parallelism
│
└─ YES → What's your P99 requirement?
         │
         ├─ >100ms  → Use large payloads (>1KB)
         │           Trade-off acceptable
         │
         ├─ 10-100ms → Profile and test
         │            Evaluate trade-off
         │
         └─ <10ms   → Use small payloads (<1KB)
                     Avoid GIL release
```

## Latency Impact Examples

### Typical P99 Latency Observations

| Scenario | Small/GIL | Large/NoGIL | Impact |
|----------|-----------|-------------|--------|
| Light load | 7.8 ms | 15.1 ms | 1.9x worse |
| Heavy load | 8.1 ms | 20.9 ms | 2.6x worse |
| Avg case | 683 µs | 856 µs | 1.3x worse |

**Key Point:** Average latency may be similar, but **tail latency (P99) can be significantly worse**.

## Monitoring Your Application

### Add This to Your Code

```python
import time
import statistics

p99_latencies = []

async def track_latency(operation):
    start = time.perf_counter()
    result = await operation
    latency_ms = (time.perf_counter() - start) * 1000
    
    p99_latencies.append(latency_ms)
    
    # Check P99 every 1000 operations
    if len(p99_latencies) >= 1000:
        sorted_lat = sorted(p99_latencies)
        p99 = sorted_lat[990]
        
        if p99 > YOUR_THRESHOLD_MS:
            logger.warning(f"P99 latency high: {p99:.2f}ms")
            # Consider switching to smaller payloads
        
        p99_latencies.clear()
    
    return result
```

## Common Patterns

### Pattern 1: Hybrid Approach
```python
# Critical path: small payloads
urgent_data = msgpack.packb({"type": "urgent", "data": small})

# Background: large payloads  
batch_data = msgpack.packb({"type": "batch", "data": large})
```

### Pattern 2: Conditional Batching
```python
if len(messages) < 10:
    # Small batch: keep payload <1KB
    for msg in messages:
        packed = msgpack.packb(msg)
        await send(packed)
else:
    # Large batch: >1KB, benefit from GIL release
    packed = msgpack.packb(messages)
    await send(packed)
```

### Pattern 3: Separate Thread Pools
```python
critical_pool = ThreadPoolExecutor(max_workers=2)
background_pool = ThreadPoolExecutor(max_workers=8)

# Critical
await asyncio.to_thread(msgpack.packb, small_data, 
                       executor=critical_pool)

# Background
await asyncio.to_thread(msgpack.packb, large_data,
                       executor=background_pool)
```

## Red Flags

### ⚠️ Warning Signs You Shouldn't Use GIL Release

- Users complaining about "occasional lag"
- P99 latency alerts triggering
- Tail latency exceeding SLA
- Real-time requirements not met
- Gaming/interactive apps feeling "sluggish"

### ✅ Green Flags You Should Use GIL Release

- High CPU utilization needed
- Processing large datasets
- Batch processing jobs
- Background workers
- Throughput bottlenecks
- Multi-threaded server

## Further Reading

- **Full analysis:** [LATENCY_ANALYSIS.md](LATENCY_ANALYSIS.md)
- **Benchmark results:** [ASYNCIO_BENCHMARK_RESULTS.md](ASYNCIO_BENCHMARK_RESULTS.md)
- **Quick start:** [BENCHMARK_README.md](BENCHMARK_README.md)

## Summary

**Default recommendation:** Use GIL release (large payloads >1KB) for most applications. The parallelism benefits outweigh the latency trade-off in typical use cases.

**Exception:** Latency-critical applications with P99 requirements <10ms should use small payloads (<1KB) to avoid GIL release.

**When in doubt:** Profile in production and measure P99 latency. Adjust based on actual requirements.
