// Package memory provides memory optimization utilities for FluxFuzzer.
// It includes buffer pooling, streaming, and monitoring capabilities.
package memory

import (
	"bytes"
	"sync"
)

// BufferPool provides a pool of reusable byte buffers to reduce GC pressure.
type BufferPool struct {
	pool    sync.Pool
	maxSize int
	stats   *PoolStats
	statsMu sync.RWMutex
}

// PoolStats tracks buffer pool statistics
type PoolStats struct {
	Gets       int64 `json:"gets"`
	Puts       int64 `json:"puts"`
	News       int64 `json:"news"`
	Discards   int64 `json:"discards"`
	TotalBytes int64 `json:"total_bytes"`
}

// NewBufferPool creates a new buffer pool
func NewBufferPool(initialSize, maxSize int) *BufferPool {
	bp := &BufferPool{
		maxSize: maxSize,
		stats:   &PoolStats{},
	}

	bp.pool = sync.Pool{
		New: func() interface{} {
			bp.statsMu.Lock()
			bp.stats.News++
			bp.statsMu.Unlock()
			return bytes.NewBuffer(make([]byte, 0, initialSize))
		},
	}

	return bp
}

// Get retrieves a buffer from the pool
func (bp *BufferPool) Get() *bytes.Buffer {
	bp.statsMu.Lock()
	bp.stats.Gets++
	bp.statsMu.Unlock()

	buf := bp.pool.Get().(*bytes.Buffer)
	buf.Reset()
	return buf
}

// Put returns a buffer to the pool
func (bp *BufferPool) Put(buf *bytes.Buffer) {
	if buf == nil {
		return
	}

	bp.statsMu.Lock()
	bp.stats.TotalBytes += int64(buf.Len())
	bp.statsMu.Unlock()

	// Don't pool oversized buffers
	if buf.Cap() > bp.maxSize {
		bp.statsMu.Lock()
		bp.stats.Discards++
		bp.statsMu.Unlock()
		return
	}

	bp.statsMu.Lock()
	bp.stats.Puts++
	bp.statsMu.Unlock()

	buf.Reset()
	bp.pool.Put(buf)
}

// GetStats returns pool statistics
func (bp *BufferPool) GetStats() PoolStats {
	bp.statsMu.RLock()
	defer bp.statsMu.RUnlock()
	return *bp.stats
}

// ByteSlicePool provides a pool of reusable byte slices
type ByteSlicePool struct {
	pools   []*sync.Pool
	sizes   []int
	stats   *SlicePoolStats
	statsMu sync.RWMutex
}

// SlicePoolStats tracks slice pool statistics
type SlicePoolStats struct {
	Gets     map[int]int64 `json:"gets"`
	Puts     map[int]int64 `json:"puts"`
	Misses   int64         `json:"misses"`
	Discards int64         `json:"discards"`
}

// Predefined slice sizes for pooling
var defaultSliceSizes = []int{
	64,     // Small payloads
	256,    // Headers
	1024,   // 1KB - typical response
	4096,   // 4KB - medium response
	16384,  // 16KB - large response
	65536,  // 64KB - very large
	262144, // 256KB - extra large
}

// NewByteSlicePool creates a new byte slice pool
func NewByteSlicePool() *ByteSlicePool {
	bsp := &ByteSlicePool{
		sizes: defaultSliceSizes,
		stats: &SlicePoolStats{
			Gets: make(map[int]int64),
			Puts: make(map[int]int64),
		},
	}

	bsp.pools = make([]*sync.Pool, len(defaultSliceSizes))
	for i, size := range defaultSliceSizes {
		s := size // Capture for closure
		bsp.pools[i] = &sync.Pool{
			New: func() interface{} {
				return make([]byte, s)
			},
		}
	}

	return bsp
}

// Get retrieves a byte slice of at least the requested size
func (bsp *ByteSlicePool) Get(size int) []byte {
	// Find the smallest pool that fits
	for i, poolSize := range bsp.sizes {
		if size <= poolSize {
			bsp.statsMu.Lock()
			bsp.stats.Gets[poolSize]++
			bsp.statsMu.Unlock()

			slice := bsp.pools[i].Get().([]byte)
			return slice[:size]
		}
	}

	// Size too large for pools, allocate directly
	bsp.statsMu.Lock()
	bsp.stats.Misses++
	bsp.statsMu.Unlock()

	return make([]byte, size)
}

// Put returns a byte slice to the pool
func (bsp *ByteSlicePool) Put(slice []byte) {
	if slice == nil {
		return
	}

	cap := cap(slice)

	// Find the matching pool
	for i, poolSize := range bsp.sizes {
		if cap == poolSize {
			bsp.statsMu.Lock()
			bsp.stats.Puts[poolSize]++
			bsp.statsMu.Unlock()

			// Reset slice to full capacity
			bsp.pools[i].Put(slice[:cap])
			return
		}
	}

	// Non-standard size, discard
	bsp.statsMu.Lock()
	bsp.stats.Discards++
	bsp.statsMu.Unlock()
}

// GetStats returns pool statistics
func (bsp *ByteSlicePool) GetStats() SlicePoolStats {
	bsp.statsMu.RLock()
	defer bsp.statsMu.RUnlock()

	// Deep copy the maps
	stats := SlicePoolStats{
		Gets:     make(map[int]int64),
		Puts:     make(map[int]int64),
		Misses:   bsp.stats.Misses,
		Discards: bsp.stats.Discards,
	}
	for k, v := range bsp.stats.Gets {
		stats.Gets[k] = v
	}
	for k, v := range bsp.stats.Puts {
		stats.Puts[k] = v
	}

	return stats
}

// Global pools for convenience
var (
	globalBufferPool    *BufferPool
	globalByteSlicePool *ByteSlicePool
	initOnce            sync.Once
)

// initGlobalPools initializes global pools
func initGlobalPools() {
	initOnce.Do(func() {
		globalBufferPool = NewBufferPool(4096, 1<<20) // 4KB initial, 1MB max
		globalByteSlicePool = NewByteSlicePool()
	})
}

// GetBuffer retrieves a buffer from the global pool
func GetBuffer() *bytes.Buffer {
	initGlobalPools()
	return globalBufferPool.Get()
}

// PutBuffer returns a buffer to the global pool
func PutBuffer(buf *bytes.Buffer) {
	initGlobalPools()
	globalBufferPool.Put(buf)
}

// GetBytes retrieves a byte slice from the global pool
func GetBytes(size int) []byte {
	initGlobalPools()
	return globalByteSlicePool.Get(size)
}

// PutBytes returns a byte slice to the global pool
func PutBytes(slice []byte) {
	initGlobalPools()
	globalByteSlicePool.Put(slice)
}

// GetGlobalStats returns statistics from global pools
func GetGlobalStats() map[string]interface{} {
	initGlobalPools()
	return map[string]interface{}{
		"buffer_pool":     globalBufferPool.GetStats(),
		"byte_slice_pool": globalByteSlicePool.GetStats(),
	}
}
