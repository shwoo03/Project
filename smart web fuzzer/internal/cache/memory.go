// Package cache provides caching utilities for FluxFuzzer.
// It includes memory cache, disk cache, and similarity hashing.
package cache

import (
	"container/list"
	"crypto/sha256"
	"encoding/hex"
	"sync"
	"time"
)

// CacheEntry represents a cache entry
type CacheEntry struct {
	Key       string
	Value     []byte
	Size      int64
	CreatedAt time.Time
	ExpiresAt time.Time
	HitCount  int64
}

// MemoryCache provides an in-memory LRU cache
type MemoryCache struct {
	capacity    int64
	currentSize int64
	ttl         time.Duration
	items       map[string]*list.Element
	order       *list.List
	stats       *CacheStats
	mu          sync.RWMutex
}

// CacheStats tracks cache statistics
type CacheStats struct {
	Hits      int64 `json:"hits"`
	Misses    int64 `json:"misses"`
	Evictions int64 `json:"evictions"`
	Size      int64 `json:"size"`
	ItemCount int   `json:"item_count"`
}

// MemoryCacheConfig holds cache configuration
type MemoryCacheConfig struct {
	Capacity int64         // Maximum size in bytes
	TTL      time.Duration // Time to live
}

// DefaultMemoryCacheConfig returns default configuration
func DefaultMemoryCacheConfig() *MemoryCacheConfig {
	return &MemoryCacheConfig{
		Capacity: 100 * 1024 * 1024, // 100MB
		TTL:      30 * time.Minute,
	}
}

// NewMemoryCache creates a new memory cache
func NewMemoryCache(config *MemoryCacheConfig) *MemoryCache {
	if config == nil {
		config = DefaultMemoryCacheConfig()
	}

	mc := &MemoryCache{
		capacity: config.Capacity,
		ttl:      config.TTL,
		items:    make(map[string]*list.Element),
		order:    list.New(),
		stats:    &CacheStats{},
	}

	// Start cleanup goroutine
	go mc.cleanup()

	return mc
}

// Get retrieves a value from cache
func (mc *MemoryCache) Get(key string) ([]byte, bool) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	elem, ok := mc.items[key]
	if !ok {
		mc.stats.Misses++
		return nil, false
	}

	entry := elem.Value.(*CacheEntry)

	// Check expiration
	if time.Now().After(entry.ExpiresAt) {
		mc.removeElement(elem)
		mc.stats.Misses++
		return nil, false
	}

	// Move to front (most recently used)
	mc.order.MoveToFront(elem)
	entry.HitCount++
	mc.stats.Hits++

	return entry.Value, true
}

// Set stores a value in cache
func (mc *MemoryCache) Set(key string, value []byte) {
	mc.SetWithTTL(key, value, mc.ttl)
}

// SetWithTTL stores a value with custom TTL
func (mc *MemoryCache) SetWithTTL(key string, value []byte, ttl time.Duration) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	size := int64(len(value))

	// Remove old entry if exists
	if elem, ok := mc.items[key]; ok {
		mc.removeElement(elem)
	}

	// Evict until we have space
	for mc.currentSize+size > mc.capacity && mc.order.Len() > 0 {
		mc.evictOldest()
	}

	entry := &CacheEntry{
		Key:       key,
		Value:     value,
		Size:      size,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(ttl),
	}

	elem := mc.order.PushFront(entry)
	mc.items[key] = elem
	mc.currentSize += size
	mc.stats.Size = mc.currentSize
	mc.stats.ItemCount = len(mc.items)
}

// Delete removes a value from cache
func (mc *MemoryCache) Delete(key string) bool {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	elem, ok := mc.items[key]
	if !ok {
		return false
	}

	mc.removeElement(elem)
	return true
}

// Clear clears the entire cache
func (mc *MemoryCache) Clear() {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	mc.items = make(map[string]*list.Element)
	mc.order.Init()
	mc.currentSize = 0
	mc.stats.Size = 0
	mc.stats.ItemCount = 0
}

// GetStats returns cache statistics
func (mc *MemoryCache) GetStats() CacheStats {
	mc.mu.RLock()
	defer mc.mu.RUnlock()

	return CacheStats{
		Hits:      mc.stats.Hits,
		Misses:    mc.stats.Misses,
		Evictions: mc.stats.Evictions,
		Size:      mc.currentSize,
		ItemCount: len(mc.items),
	}
}

// removeElement removes an element from cache
func (mc *MemoryCache) removeElement(elem *list.Element) {
	entry := elem.Value.(*CacheEntry)
	delete(mc.items, entry.Key)
	mc.order.Remove(elem)
	mc.currentSize -= entry.Size
}

// evictOldest evicts the least recently used entry
func (mc *MemoryCache) evictOldest() {
	elem := mc.order.Back()
	if elem != nil {
		mc.removeElement(elem)
		mc.stats.Evictions++
	}
}

// cleanup periodically removes expired entries
func (mc *MemoryCache) cleanup() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		mc.mu.Lock()
		now := time.Now()
		var toRemove []*list.Element

		for elem := mc.order.Back(); elem != nil; elem = elem.Prev() {
			entry := elem.Value.(*CacheEntry)
			if now.After(entry.ExpiresAt) {
				toRemove = append(toRemove, elem)
			}
		}

		for _, elem := range toRemove {
			mc.removeElement(elem)
		}
		mc.mu.Unlock()
	}
}

// ResponseCache caches HTTP responses
type ResponseCache struct {
	cache *MemoryCache
}

// NewResponseCache creates a new response cache
func NewResponseCache(config *MemoryCacheConfig) *ResponseCache {
	return &ResponseCache{
		cache: NewMemoryCache(config),
	}
}

// CacheKey generates a cache key for a request
func (rc *ResponseCache) CacheKey(method, url string, body []byte) string {
	h := sha256.New()
	h.Write([]byte(method))
	h.Write([]byte(url))
	if body != nil {
		h.Write(body)
	}
	return hex.EncodeToString(h.Sum(nil))
}

// Get retrieves a cached response
func (rc *ResponseCache) Get(method, url string, body []byte) ([]byte, bool) {
	key := rc.CacheKey(method, url, body)
	return rc.cache.Get(key)
}

// Set caches a response
func (rc *ResponseCache) Set(method, url string, body, response []byte) {
	key := rc.CacheKey(method, url, body)
	rc.cache.Set(key, response)
}

// GetStats returns cache statistics
func (rc *ResponseCache) GetStats() CacheStats {
	return rc.cache.GetStats()
}

// BaselineCache stores baseline responses for comparison
type BaselineCache struct {
	baselines map[string]*BaselineEntry
	mu        sync.RWMutex
}

// BaselineEntry represents a baseline response
type BaselineEntry struct {
	URL           string
	StatusCode    int
	ContentHash   string
	ContentLength int64
	Headers       map[string]string
	ResponseTime  time.Duration
	CapturedAt    time.Time
}

// NewBaselineCache creates a new baseline cache
func NewBaselineCache() *BaselineCache {
	return &BaselineCache{
		baselines: make(map[string]*BaselineEntry),
	}
}

// Set stores a baseline
func (bc *BaselineCache) Set(url string, entry *BaselineEntry) {
	bc.mu.Lock()
	defer bc.mu.Unlock()
	bc.baselines[url] = entry
}

// Get retrieves a baseline
func (bc *BaselineCache) Get(url string) (*BaselineEntry, bool) {
	bc.mu.RLock()
	defer bc.mu.RUnlock()
	entry, ok := bc.baselines[url]
	return entry, ok
}

// Compare compares a response against baseline
func (bc *BaselineCache) Compare(url string, statusCode int, contentHash string, contentLength int64, responseTime time.Duration) *BaselineDiff {
	baseline, ok := bc.Get(url)
	if !ok {
		return nil
	}

	diff := &BaselineDiff{
		URL: url,
	}

	if baseline.StatusCode != statusCode {
		diff.StatusChanged = true
		diff.OldStatus = baseline.StatusCode
		diff.NewStatus = statusCode
	}

	if baseline.ContentHash != contentHash {
		diff.ContentChanged = true
	}

	if baseline.ContentLength != contentLength {
		diff.SizeChanged = true
		diff.SizeDelta = contentLength - baseline.ContentLength
	}

	// Check for significant timing change (>50% difference)
	if baseline.ResponseTime > 0 {
		timeDelta := responseTime - baseline.ResponseTime
		if timeDelta > baseline.ResponseTime/2 || timeDelta < -baseline.ResponseTime/2 {
			diff.TimingChanged = true
			diff.TimingDelta = timeDelta
		}
	}

	return diff
}

// BaselineDiff represents differences from baseline
type BaselineDiff struct {
	URL            string
	StatusChanged  bool
	OldStatus      int
	NewStatus      int
	ContentChanged bool
	SizeChanged    bool
	SizeDelta      int64
	TimingChanged  bool
	TimingDelta    time.Duration
}

// HasChanges returns true if any differences were found
func (bd *BaselineDiff) HasChanges() bool {
	return bd.StatusChanged || bd.ContentChanged || bd.SizeChanged || bd.TimingChanged
}

// ContentHash generates a hash for content
func ContentHash(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}
