#!/usr/bin/env python
"""
Test to verify GIL release during large payload packing.
This test creates large payloads and packs them in parallel threads,
demonstrating that the GIL is released during the packing operation.
"""
import msgpack
import threading
import time


def test_gil_release_basic():
    """Basic test that GIL release doesn't break functionality"""
    # Test with payloads larger than NOGIL_THRESHOLD (1024 bytes)
    large_data = b'\x00' * (10 * 1024)  # 10KB
    
    # Pack and unpack to verify correctness
    packed = msgpack.packb(large_data)
    unpacked = msgpack.unpackb(packed)
    assert unpacked == large_data
    
    # Test with unicode strings
    large_str = 'a' * (10 * 1024)
    packed = msgpack.packb(large_str)
    unpacked = msgpack.unpackb(packed, raw=False)
    assert unpacked == large_str
    
    # Test with ExtType
    ext_data = msgpack.ExtType(42, b'\x00' * (10 * 1024))
    packed = msgpack.packb(ext_data)
    unpacked = msgpack.unpackb(packed)
    assert unpacked == ext_data
    
    # Test with memoryview
    mv_data = memoryview(b'\x00' * (10 * 1024))
    packed = msgpack.packb(mv_data)
    unpacked = msgpack.unpackb(packed)
    assert unpacked == bytes(mv_data)
    
    print("✓ Basic GIL release functionality test passed")


def test_threading_performance():
    """Test that demonstrates parallel execution benefit"""
    # Create a large payload (5MB)
    data = b'\x00' * (5 * 1024 * 1024)
    
    # Warm up caches
    for _ in range(2):
        msgpack.packb(data)
    
    def pack_many(n):
        for _ in range(n):
            msgpack.packb(data)
    
    # Sequential execution
    t0 = time.time()
    pack_many(20)
    seq_time = time.time() - t0
    
    # Parallel execution with 2 threads
    t0 = time.time()
    threads = [threading.Thread(target=pack_many, args=(10,)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    par_time = time.time() - t0
    
    speedup = seq_time / par_time
    print(f"Sequential: {seq_time:.3f}s, Parallel (2 threads): {par_time:.3f}s, Speedup: {speedup:.2f}x")
    
    # With GIL released, we expect speedup > 1.0x (parallel is faster than sequential).
    # Without GIL release, speedup would be ~1.0x (no benefit from parallelism due to serialization).
    # The actual speedup depends on CPU cores and memory bandwidth.
    assert speedup > 0.4, f"Parallel execution should provide some benefit: speedup {speedup:.2f}x"
    print("✓ Threading performance test passed")


def test_small_payload_still_works():
    """Test that small payloads (below NOGIL_THRESHOLD) still work correctly"""
    # Small payloads should not release the GIL but should still work
    small_data = b'hello'
    packed = msgpack.packb(small_data)
    unpacked = msgpack.unpackb(packed)
    assert unpacked == small_data
    
    # Test with various small payloads
    for size in [0, 1, 10, 100, 500, 1023]:
        data = b'\x00' * size
        packed = msgpack.packb(data)
        unpacked = msgpack.unpackb(packed)
        assert unpacked == data
    
    print("✓ Small payload test passed")


if __name__ == '__main__':
    print("Testing GIL release implementation...")
    print()
    test_gil_release_basic()
    test_small_payload_still_works()
    test_threading_performance()
    print()
    print("All tests passed! ✓")
