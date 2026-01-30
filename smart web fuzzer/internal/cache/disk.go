// Package cache provides disk-based persistent caching.
package cache

import (
	"crypto/sha256"
	"encoding/gob"
	"encoding/hex"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// DiskCache provides persistent disk-based caching
type DiskCache struct {
	baseDir     string
	maxSize     int64
	currentSize int64
	index       map[string]*DiskCacheEntry
	stats       *CacheStats
	mu          sync.RWMutex
}

// DiskCacheEntry represents a disk cache entry
type DiskCacheEntry struct {
	Key       string
	FilePath  string
	Size      int64
	CreatedAt time.Time
	ExpiresAt time.Time
	HitCount  int64
}

// DiskCacheConfig holds disk cache configuration
type DiskCacheConfig struct {
	BaseDir string
	MaxSize int64         // Maximum total size in bytes
	TTL     time.Duration // Time to live
}

// DefaultDiskCacheConfig returns default configuration
func DefaultDiskCacheConfig() *DiskCacheConfig {
	cacheDir := filepath.Join(os.TempDir(), "fluxfuzzer_cache")
	return &DiskCacheConfig{
		BaseDir: cacheDir,
		MaxSize: 1 << 30, // 1GB
		TTL:     24 * time.Hour,
	}
}

// NewDiskCache creates a new disk cache
func NewDiskCache(config *DiskCacheConfig) (*DiskCache, error) {
	if config == nil {
		config = DefaultDiskCacheConfig()
	}

	// Create cache directory
	if err := os.MkdirAll(config.BaseDir, 0755); err != nil {
		return nil, err
	}

	dc := &DiskCache{
		baseDir: config.BaseDir,
		maxSize: config.MaxSize,
		index:   make(map[string]*DiskCacheEntry),
		stats:   &CacheStats{},
	}

	// Load existing index
	dc.loadIndex()

	// Start cleanup goroutine
	go dc.cleanup()

	return dc, nil
}

// Get retrieves a value from disk cache
func (dc *DiskCache) Get(key string) ([]byte, bool) {
	dc.mu.RLock()
	entry, ok := dc.index[key]
	dc.mu.RUnlock()

	if !ok {
		dc.mu.Lock()
		dc.stats.Misses++
		dc.mu.Unlock()
		return nil, false
	}

	// Check expiration
	if time.Now().After(entry.ExpiresAt) {
		dc.Delete(key)
		dc.mu.Lock()
		dc.stats.Misses++
		dc.mu.Unlock()
		return nil, false
	}

	// Read from disk
	data, err := os.ReadFile(entry.FilePath)
	if err != nil {
		dc.Delete(key)
		dc.mu.Lock()
		dc.stats.Misses++
		dc.mu.Unlock()
		return nil, false
	}

	dc.mu.Lock()
	entry.HitCount++
	dc.stats.Hits++
	dc.mu.Unlock()

	return data, true
}

// Set stores a value to disk cache
func (dc *DiskCache) Set(key string, value []byte, ttl time.Duration) error {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	size := int64(len(value))

	// Evict if necessary
	for dc.currentSize+size > dc.maxSize && len(dc.index) > 0 {
		dc.evictOldest()
	}

	// Generate file path
	hash := sha256.Sum256([]byte(key))
	fileName := hex.EncodeToString(hash[:]) + ".cache"
	filePath := filepath.Join(dc.baseDir, fileName)

	// Write to disk
	if err := os.WriteFile(filePath, value, 0644); err != nil {
		return err
	}

	// Update index
	entry := &DiskCacheEntry{
		Key:       key,
		FilePath:  filePath,
		Size:      size,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(ttl),
	}

	// Remove old entry if exists
	if oldEntry, ok := dc.index[key]; ok {
		dc.currentSize -= oldEntry.Size
		os.Remove(oldEntry.FilePath)
	}

	dc.index[key] = entry
	dc.currentSize += size
	dc.stats.Size = dc.currentSize
	dc.stats.ItemCount = len(dc.index)

	return nil
}

// Delete removes a value from disk cache
func (dc *DiskCache) Delete(key string) bool {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	entry, ok := dc.index[key]
	if !ok {
		return false
	}

	os.Remove(entry.FilePath)
	dc.currentSize -= entry.Size
	delete(dc.index, key)
	dc.stats.Size = dc.currentSize
	dc.stats.ItemCount = len(dc.index)

	return true
}

// Clear clears the entire cache
func (dc *DiskCache) Clear() error {
	dc.mu.Lock()
	defer dc.mu.Unlock()

	// Remove all files
	for _, entry := range dc.index {
		os.Remove(entry.FilePath)
	}

	dc.index = make(map[string]*DiskCacheEntry)
	dc.currentSize = 0
	dc.stats.Size = 0
	dc.stats.ItemCount = 0

	return nil
}

// GetStats returns cache statistics
func (dc *DiskCache) GetStats() CacheStats {
	dc.mu.RLock()
	defer dc.mu.RUnlock()

	return CacheStats{
		Hits:      dc.stats.Hits,
		Misses:    dc.stats.Misses,
		Evictions: dc.stats.Evictions,
		Size:      dc.currentSize,
		ItemCount: len(dc.index),
	}
}

// evictOldest evicts the oldest entry
func (dc *DiskCache) evictOldest() {
	var oldest *DiskCacheEntry
	var oldestKey string

	for key, entry := range dc.index {
		if oldest == nil || entry.CreatedAt.Before(oldest.CreatedAt) {
			oldest = entry
			oldestKey = key
		}
	}

	if oldest != nil {
		os.Remove(oldest.FilePath)
		dc.currentSize -= oldest.Size
		delete(dc.index, oldestKey)
		dc.stats.Evictions++
	}
}

// cleanup periodically removes expired entries
func (dc *DiskCache) cleanup() {
	ticker := time.NewTicker(10 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		dc.mu.Lock()
		now := time.Now()
		var toRemove []string

		for key, entry := range dc.index {
			if now.After(entry.ExpiresAt) {
				toRemove = append(toRemove, key)
			}
		}

		for _, key := range toRemove {
			entry := dc.index[key]
			os.Remove(entry.FilePath)
			dc.currentSize -= entry.Size
			delete(dc.index, key)
		}

		dc.stats.Size = dc.currentSize
		dc.stats.ItemCount = len(dc.index)
		dc.mu.Unlock()
	}
}

// loadIndex loads the cache index from disk
func (dc *DiskCache) loadIndex() {
	indexPath := filepath.Join(dc.baseDir, "index.gob")
	file, err := os.Open(indexPath)
	if err != nil {
		return
	}
	defer file.Close()

	decoder := gob.NewDecoder(file)
	var entries []*DiskCacheEntry
	if err := decoder.Decode(&entries); err != nil {
		return
	}

	for _, entry := range entries {
		// Verify file exists
		if _, err := os.Stat(entry.FilePath); err == nil {
			dc.index[entry.Key] = entry
			dc.currentSize += entry.Size
		}
	}

	dc.stats.Size = dc.currentSize
	dc.stats.ItemCount = len(dc.index)
}

// SaveIndex saves the cache index to disk
func (dc *DiskCache) SaveIndex() error {
	dc.mu.RLock()
	defer dc.mu.RUnlock()

	entries := make([]*DiskCacheEntry, 0, len(dc.index))
	for _, entry := range dc.index {
		entries = append(entries, entry)
	}

	indexPath := filepath.Join(dc.baseDir, "index.gob")
	file, err := os.Create(indexPath)
	if err != nil {
		return err
	}
	defer file.Close()

	encoder := gob.NewEncoder(file)
	return encoder.Encode(entries)
}

// TieredCache combines memory and disk caching
type TieredCache struct {
	memory *MemoryCache
	disk   *DiskCache
	mu     sync.RWMutex
}

// NewTieredCache creates a new tiered cache
func NewTieredCache(memConfig *MemoryCacheConfig, diskConfig *DiskCacheConfig) (*TieredCache, error) {
	disk, err := NewDiskCache(diskConfig)
	if err != nil {
		return nil, err
	}

	return &TieredCache{
		memory: NewMemoryCache(memConfig),
		disk:   disk,
	}, nil
}

// Get retrieves from memory first, then disk
func (tc *TieredCache) Get(key string) ([]byte, bool) {
	// Try memory first
	if data, ok := tc.memory.Get(key); ok {
		return data, true
	}

	// Try disk
	if data, ok := tc.disk.Get(key); ok {
		// Promote to memory
		tc.memory.Set(key, data)
		return data, true
	}

	return nil, false
}

// Set stores in memory and optionally on disk
func (tc *TieredCache) Set(key string, value []byte, persist bool, ttl time.Duration) error {
	tc.memory.SetWithTTL(key, value, ttl)

	if persist {
		return tc.disk.Set(key, value, ttl)
	}

	return nil
}

// GetStats returns combined statistics
func (tc *TieredCache) GetStats() map[string]CacheStats {
	return map[string]CacheStats{
		"memory": tc.memory.GetStats(),
		"disk":   tc.disk.GetStats(),
	}
}
