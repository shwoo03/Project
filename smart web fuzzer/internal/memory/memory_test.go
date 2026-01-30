package memory

import (
	"bytes"
	"io"
	"testing"
	"time"
)

func TestBufferPool(t *testing.T) {
	pool := NewBufferPool(1024, 1<<20)

	// Get and use a buffer
	buf := pool.Get()
	if buf == nil {
		t.Fatal("Get returned nil")
	}

	buf.WriteString("test data")
	if buf.String() != "test data" {
		t.Error("Buffer write failed")
	}

	// Return buffer
	pool.Put(buf)

	stats := pool.GetStats()
	if stats.Gets != 1 {
		t.Errorf("Expected 1 get, got %d", stats.Gets)
	}
	if stats.Puts != 1 {
		t.Errorf("Expected 1 put, got %d", stats.Puts)
	}
}

func TestBufferPool_OversizedBuffer(t *testing.T) {
	pool := NewBufferPool(1024, 4096) // Max 4KB

	// Create oversized buffer
	buf := bytes.NewBuffer(make([]byte, 0, 8192)) // 8KB capacity
	buf.WriteString("data")

	pool.Put(buf)

	stats := pool.GetStats()
	if stats.Discards != 1 {
		t.Errorf("Expected 1 discard, got %d", stats.Discards)
	}
}

func TestByteSlicePool(t *testing.T) {
	pool := NewByteSlicePool()

	// Test various sizes
	sizes := []int{32, 100, 500, 2000, 10000}
	for _, size := range sizes {
		slice := pool.Get(size)
		if len(slice) != size {
			t.Errorf("Expected len %d, got %d", size, len(slice))
		}
		pool.Put(slice)
	}
}

func TestByteSlicePool_LargeSize(t *testing.T) {
	pool := NewByteSlicePool()

	// Request larger than any pool
	slice := pool.Get(1 << 20) // 1MB
	if len(slice) != 1<<20 {
		t.Errorf("Expected 1MB slice")
	}

	stats := pool.GetStats()
	if stats.Misses != 1 {
		t.Errorf("Expected 1 miss, got %d", stats.Misses)
	}
}

func TestGlobalPools(t *testing.T) {
	// Test global buffer
	buf := GetBuffer()
	if buf == nil {
		t.Fatal("GetBuffer returned nil")
	}
	buf.WriteString("global test")
	PutBuffer(buf)

	// Test global bytes
	slice := GetBytes(100)
	if len(slice) != 100 {
		t.Errorf("Expected 100 bytes, got %d", len(slice))
	}
	PutBytes(slice)

	// Get stats
	stats := GetGlobalStats()
	if stats == nil {
		t.Error("GetGlobalStats returned nil")
	}
}

func TestChunkedReader(t *testing.T) {
	data := bytes.Repeat([]byte("x"), 10000)
	reader := bytes.NewReader(data)

	config := &StreamConfig{
		ChunkSize:     1000,
		MaxTotalBytes: 100000,
	}

	cr := NewChunkedReader(reader, config)

	totalRead := 0
	for {
		chunk, err := cr.ReadChunk()
		if err == io.EOF {
			break
		}
		if chunk != nil {
			totalRead += len(chunk)
			PutBytes(chunk)
		}
	}

	if totalRead != 10000 {
		t.Errorf("Expected 10000 bytes, got %d", totalRead)
	}

	if cr.BytesRead() != 10000 {
		t.Errorf("BytesRead mismatch: %d", cr.BytesRead())
	}
}

func TestLimitedBuffer(t *testing.T) {
	buf := NewLimitedBuffer(100)

	// Write within limit
	n, err := buf.Write([]byte("hello"))
	if err != nil || n != 5 {
		t.Error("Write failed")
	}

	// Write more
	n, _ = buf.Write(bytes.Repeat([]byte("x"), 50))
	if n != 50 {
		t.Errorf("Expected 50, got %d", n)
	}

	if buf.Len() != 55 {
		t.Errorf("Expected 55, got %d", buf.Len())
	}

	// Write past limit
	n, _ = buf.Write(bytes.Repeat([]byte("y"), 100))
	if n != 45 { // Only 45 bytes should fit
		t.Errorf("Expected 45, got %d", n)
	}

	if !buf.IsFull() {
		t.Error("Buffer should be full")
	}
}

func TestRingBuffer(t *testing.T) {
	rb := NewRingBuffer(10)

	// Write less than capacity
	n, _ := rb.Write([]byte("hello"))
	if n != 5 {
		t.Errorf("Expected 5, got %d", n)
	}

	if rb.Len() != 5 {
		t.Errorf("Expected len 5, got %d", rb.Len())
	}

	// Read back
	buf := make([]byte, 10)
	n, _ = rb.Read(buf)
	if n != 5 {
		t.Errorf("Expected read 5, got %d", n)
	}
	if string(buf[:n]) != "hello" {
		t.Errorf("Expected 'hello', got '%s'", string(buf[:n]))
	}

	// Test overflow behavior
	rb.Reset()
	rb.Write(bytes.Repeat([]byte("x"), 15)) // Write more than capacity

	if rb.Len() != 10 {
		t.Errorf("Expected len 10 (capacity), got %d", rb.Len())
	}
}

func TestMonitor(t *testing.T) {
	threshold := MemoryThreshold{
		HeapAllocBytes: 1 << 30, // 1GB
		HeapPercent:    80,
	}

	monitor := NewMonitor(100*time.Millisecond, threshold)
	monitor.Start()

	// Wait for some stats to be collected
	time.Sleep(250 * time.Millisecond)

	stats := monitor.GetCurrentStats()
	if stats.HeapAlloc == 0 {
		t.Error("HeapAlloc should not be 0")
	}

	history := monitor.GetHistory()
	if len(history) == 0 {
		t.Error("History should not be empty")
	}

	latest := monitor.GetLatest()
	if latest == nil {
		t.Error("Latest should not be nil")
	}

	monitor.Stop()
}

func TestQuickStats(t *testing.T) {
	stats := QuickStats()
	if stats == nil {
		t.Fatal("QuickStats returned nil")
	}

	if _, ok := stats["alloc_mb"]; !ok {
		t.Error("Missing alloc_mb")
	}
	if _, ok := stats["goroutines"]; !ok {
		t.Error("Missing goroutines")
	}
}

func BenchmarkBufferPool(b *testing.B) {
	pool := NewBufferPool(1024, 1<<20)

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			buf := pool.Get()
			buf.WriteString("benchmark data")
			pool.Put(buf)
		}
	})
}

func BenchmarkByteSlicePool(b *testing.B) {
	pool := NewByteSlicePool()

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			slice := pool.Get(1024)
			copy(slice, []byte("benchmark"))
			pool.Put(slice)
		}
	})
}
