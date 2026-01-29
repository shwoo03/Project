// Package state provides a thread-safe dynamic value pool for fuzzing.
// It stores extracted values with TTL-based expiration and deduplication.
package state

import (
	"sync"
	"time"
)

// PoolEntry represents a single entry in the pool
type PoolEntry struct {
	Value     string
	Source    string // Where the value was extracted from
	CreatedAt time.Time
	ExpiresAt time.Time
	UseCount  int
}

// IsExpired checks if the entry has expired
func (e *PoolEntry) IsExpired() bool {
	if e.ExpiresAt.IsZero() {
		return false
	}
	return time.Now().After(e.ExpiresAt)
}

// PoolConfig holds configuration for the Pool
type PoolConfig struct {
	// DefaultTTL is the default time-to-live for entries
	DefaultTTL time.Duration

	// MaxEntriesPerKey is the maximum number of entries per key
	MaxEntriesPerKey int

	// MaxTotalEntries is the maximum total entries across all keys
	MaxTotalEntries int

	// CleanupInterval is how often to run cleanup
	CleanupInterval time.Duration

	// AllowDuplicates controls whether duplicate values are allowed per key
	AllowDuplicates bool
}

// DefaultPoolConfig returns sensible default configuration
func DefaultPoolConfig() *PoolConfig {
	return &PoolConfig{
		DefaultTTL:       30 * time.Minute,
		MaxEntriesPerKey: 100,
		MaxTotalEntries:  10000,
		CleanupInterval:  5 * time.Minute,
		AllowDuplicates:  false,
	}
}

// Pool is a thread-safe dynamic value storage
type Pool struct {
	config  *PoolConfig
	mu      sync.RWMutex
	entries map[string][]*PoolEntry
	stats   PoolStats

	// Cleanup control
	stopCleanup chan struct{}
	cleanupDone chan struct{}
}

// PoolStats tracks pool statistics
type PoolStats struct {
	TotalEntries   int
	KeyCount       int
	ExpiredRemoved int
	AddedCount     int
	RetrievedCount int
}

// NewPool creates a new Pool with the given configuration
func NewPool(config *PoolConfig) *Pool {
	if config == nil {
		config = DefaultPoolConfig()
	}

	p := &Pool{
		config:      config,
		entries:     make(map[string][]*PoolEntry),
		stopCleanup: make(chan struct{}),
		cleanupDone: make(chan struct{}),
	}

	// Start cleanup goroutine
	if config.CleanupInterval > 0 {
		go p.cleanupLoop()
	}

	return p
}

// Add adds a value to the pool with default TTL
func (p *Pool) Add(key, value string) bool {
	return p.AddWithTTL(key, value, p.config.DefaultTTL)
}

// AddWithTTL adds a value to the pool with custom TTL
func (p *Pool) AddWithTTL(key, value string, ttl time.Duration) bool {
	return p.AddEntry(key, &PoolEntry{
		Value:     value,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(ttl),
	})
}

// AddWithSource adds a value with source information
func (p *Pool) AddWithSource(key, value, source string) bool {
	return p.AddEntry(key, &PoolEntry{
		Value:     value,
		Source:    source,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(p.config.DefaultTTL),
	})
}

// AddEntry adds a complete entry to the pool
func (p *Pool) AddEntry(key string, entry *PoolEntry) bool {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Check total entries limit
	if p.stats.TotalEntries >= p.config.MaxTotalEntries {
		// Try to evict expired entries first
		p.evictExpiredLocked()
		if p.stats.TotalEntries >= p.config.MaxTotalEntries {
			return false
		}
	}

	// Get or create entry list for key
	entries := p.entries[key]

	// Check for duplicates if not allowed
	if !p.config.AllowDuplicates {
		for _, e := range entries {
			if e.Value == entry.Value && !e.IsExpired() {
				// Update existing entry instead of adding duplicate
				e.ExpiresAt = entry.ExpiresAt
				return true
			}
		}
	}

	// Check per-key limit
	if len(entries) >= p.config.MaxEntriesPerKey {
		// Remove oldest entry
		entries = entries[1:]
	}

	// Add new entry
	p.entries[key] = append(entries, entry)
	p.stats.TotalEntries++
	p.stats.AddedCount++

	if len(entries) == 0 {
		p.stats.KeyCount++
	}

	return true
}

// Get retrieves a random value for the key
func (p *Pool) Get(key string) (string, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	entries := p.entries[key]
	if len(entries) == 0 {
		return "", false
	}

	// Find first non-expired entry
	for _, e := range entries {
		if !e.IsExpired() {
			e.UseCount++
			p.stats.RetrievedCount++
			return e.Value, true
		}
	}

	return "", false
}

// GetAll retrieves all non-expired values for the key
func (p *Pool) GetAll(key string) []string {
	p.mu.RLock()
	defer p.mu.RUnlock()

	entries := p.entries[key]
	values := make([]string, 0, len(entries))

	for _, e := range entries {
		if !e.IsExpired() {
			values = append(values, e.Value)
		}
	}

	return values
}

// GetLatest retrieves the most recently added value for the key
func (p *Pool) GetLatest(key string) (string, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	entries := p.entries[key]
	for i := len(entries) - 1; i >= 0; i-- {
		if !entries[i].IsExpired() {
			entries[i].UseCount++
			p.stats.RetrievedCount++
			return entries[i].Value, true
		}
	}

	return "", false
}

// GetEntry retrieves a complete entry for the key
func (p *Pool) GetEntry(key string) (*PoolEntry, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	entries := p.entries[key]
	for _, e := range entries {
		if !e.IsExpired() {
			e.UseCount++
			return e, true
		}
	}

	return nil, false
}

// Has checks if a key has any non-expired values
func (p *Pool) Has(key string) bool {
	p.mu.RLock()
	defer p.mu.RUnlock()

	entries := p.entries[key]
	for _, e := range entries {
		if !e.IsExpired() {
			return true
		}
	}

	return false
}

// Remove removes all entries for a key
func (p *Pool) Remove(key string) int {
	p.mu.Lock()
	defer p.mu.Unlock()

	entries := p.entries[key]
	count := len(entries)

	if count > 0 {
		delete(p.entries, key)
		p.stats.TotalEntries -= count
		p.stats.KeyCount--
	}

	return count
}

// RemoveValue removes a specific value from a key
func (p *Pool) RemoveValue(key, value string) bool {
	p.mu.Lock()
	defer p.mu.Unlock()

	entries := p.entries[key]
	for i, e := range entries {
		if e.Value == value {
			p.entries[key] = append(entries[:i], entries[i+1:]...)
			p.stats.TotalEntries--
			if len(p.entries[key]) == 0 {
				delete(p.entries, key)
				p.stats.KeyCount--
			}
			return true
		}
	}

	return false
}

// Clear removes all entries from the pool
func (p *Pool) Clear() {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.entries = make(map[string][]*PoolEntry)
	p.stats.TotalEntries = 0
	p.stats.KeyCount = 0
}

// Keys returns all keys in the pool
func (p *Pool) Keys() []string {
	p.mu.RLock()
	defer p.mu.RUnlock()

	keys := make([]string, 0, len(p.entries))
	for key := range p.entries {
		keys = append(keys, key)
	}

	return keys
}

// Size returns the total number of entries
func (p *Pool) Size() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.stats.TotalEntries
}

// KeyCount returns the number of unique keys
func (p *Pool) KeyCount() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.stats.KeyCount
}

// Stats returns pool statistics
func (p *Pool) Stats() PoolStats {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.stats
}

// Cleanup removes all expired entries
func (p *Pool) Cleanup() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.evictExpiredLocked()
}

// evictExpiredLocked removes expired entries (must be called with lock held)
func (p *Pool) evictExpiredLocked() int {
	removed := 0

	for key, entries := range p.entries {
		validEntries := make([]*PoolEntry, 0, len(entries))
		for _, e := range entries {
			if !e.IsExpired() {
				validEntries = append(validEntries, e)
			} else {
				removed++
			}
		}

		if len(validEntries) == 0 {
			delete(p.entries, key)
			p.stats.KeyCount--
		} else {
			p.entries[key] = validEntries
		}
	}

	p.stats.TotalEntries -= removed
	p.stats.ExpiredRemoved += removed

	return removed
}

// cleanupLoop runs periodic cleanup
func (p *Pool) cleanupLoop() {
	ticker := time.NewTicker(p.config.CleanupInterval)
	defer ticker.Stop()
	defer close(p.cleanupDone)

	for {
		select {
		case <-ticker.C:
			p.Cleanup()
		case <-p.stopCleanup:
			return
		}
	}
}

// Close stops the cleanup goroutine and releases resources
func (p *Pool) Close() {
	close(p.stopCleanup)
	select {
	case <-p.cleanupDone:
	case <-time.After(time.Second):
		// Timeout waiting for cleanup to finish
	}
}

// Snapshot returns a copy of all entries (for debugging/serialization)
func (p *Pool) Snapshot() map[string][]string {
	p.mu.RLock()
	defer p.mu.RUnlock()

	snapshot := make(map[string][]string)
	for key, entries := range p.entries {
		values := make([]string, 0, len(entries))
		for _, e := range entries {
			if !e.IsExpired() {
				values = append(values, e.Value)
			}
		}
		if len(values) > 0 {
			snapshot[key] = values
		}
	}

	return snapshot
}

// Import loads values from a snapshot
func (p *Pool) Import(data map[string][]string) int {
	p.mu.Lock()
	defer p.mu.Unlock()

	count := 0
	for key, values := range data {
		for _, value := range values {
			entry := &PoolEntry{
				Value:     value,
				CreatedAt: time.Now(),
				ExpiresAt: time.Now().Add(p.config.DefaultTTL),
			}
			p.entries[key] = append(p.entries[key], entry)
			count++
		}
		if len(values) > 0 {
			p.stats.KeyCount++
		}
	}

	p.stats.TotalEntries += count
	p.stats.AddedCount += count

	return count
}

// --- Value Sources ---

// ValueSource represents a way to get values for substitution
type ValueSource interface {
	GetValue(key string) (string, bool)
}

// PoolValueSource adapts Pool to ValueSource interface
type PoolValueSource struct {
	pool *Pool
}

// NewPoolValueSource creates a ValueSource from a Pool
func NewPoolValueSource(pool *Pool) *PoolValueSource {
	return &PoolValueSource{pool: pool}
}

// GetValue implements ValueSource
func (s *PoolValueSource) GetValue(key string) (string, bool) {
	return s.pool.GetLatest(key)
}
