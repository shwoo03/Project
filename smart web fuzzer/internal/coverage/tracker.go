// Package coverage provides coverage-guided fuzzing capabilities.
// It implements AFL-style instrumentation and feedback loops.
package coverage

import (
	"crypto/sha256"
	"encoding/binary"
	"sync"
	"sync/atomic"
	"time"
)

// EdgeID represents a unique edge in the control flow graph
type EdgeID uint32

// CoverageMap stores coverage information (AFL-style bitmap)
type CoverageMap struct {
	bitmap   []byte
	size     int
	hitCount int64
	newEdges int64
	mu       sync.RWMutex
}

// NewCoverageMap creates a new coverage map
func NewCoverageMap(size int) *CoverageMap {
	if size <= 0 {
		size = 65536 // Default 64KB bitmap
	}
	return &CoverageMap{
		bitmap: make([]byte, size),
		size:   size,
	}
}

// RecordEdge records an edge hit
func (cm *CoverageMap) RecordEdge(from, to uint32) bool {
	// AFL-style edge ID: (from >> 1) ^ to
	edgeID := (from >> 1) ^ to
	index := int(edgeID) % cm.size

	cm.mu.Lock()
	defer cm.mu.Unlock()

	oldVal := cm.bitmap[index]
	newVal := oldVal + 1

	// Handle overflow with bucket counting (AFL-style)
	if newVal < oldVal {
		newVal = 255
	}

	cm.bitmap[index] = newVal
	atomic.AddInt64(&cm.hitCount, 1)

	// Return true if this is a new edge or new hit count bucket
	isNew := (oldVal == 0) || (hitCountBucket(oldVal) != hitCountBucket(newVal))
	if isNew && oldVal == 0 {
		atomic.AddInt64(&cm.newEdges, 1)
	}

	return isNew
}

// hitCountBucket classifies hit counts into buckets (AFL-style)
func hitCountBucket(count byte) byte {
	switch {
	case count == 0:
		return 0
	case count == 1:
		return 1
	case count == 2:
		return 2
	case count == 3:
		return 3
	case count <= 7:
		return 4
	case count <= 15:
		return 5
	case count <= 31:
		return 6
	case count <= 127:
		return 7
	default:
		return 8
	}
}

// Merge merges another coverage map into this one
func (cm *CoverageMap) Merge(other *CoverageMap) int {
	if other == nil || len(other.bitmap) != len(cm.bitmap) {
		return 0
	}

	cm.mu.Lock()
	defer cm.mu.Unlock()

	newEdges := 0
	for i := range cm.bitmap {
		if cm.bitmap[i] == 0 && other.bitmap[i] > 0 {
			newEdges++
		}
		if other.bitmap[i] > cm.bitmap[i] {
			cm.bitmap[i] = other.bitmap[i]
		}
	}

	return newEdges
}

// Hash returns a hash of the coverage map
func (cm *CoverageMap) Hash() []byte {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	h := sha256.Sum256(cm.bitmap)
	return h[:]
}

// GetStats returns coverage statistics
func (cm *CoverageMap) GetStats() CoverageStats {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	edgesCovered := 0
	for _, v := range cm.bitmap {
		if v > 0 {
			edgesCovered++
		}
	}

	return CoverageStats{
		EdgesCovered:    edgesCovered,
		TotalEdges:      cm.size,
		HitCount:        atomic.LoadInt64(&cm.hitCount),
		NewEdges:        atomic.LoadInt64(&cm.newEdges),
		CoveragePercent: float64(edgesCovered) / float64(cm.size) * 100,
	}
}

// Reset resets the coverage map
func (cm *CoverageMap) Reset() {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	for i := range cm.bitmap {
		cm.bitmap[i] = 0
	}
	atomic.StoreInt64(&cm.hitCount, 0)
	atomic.StoreInt64(&cm.newEdges, 0)
}

// Clone creates a copy of the coverage map
func (cm *CoverageMap) Clone() *CoverageMap {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	clone := &CoverageMap{
		bitmap:   make([]byte, cm.size),
		size:     cm.size,
		hitCount: atomic.LoadInt64(&cm.hitCount),
		newEdges: atomic.LoadInt64(&cm.newEdges),
	}
	copy(clone.bitmap, cm.bitmap)
	return clone
}

// CoverageStats holds coverage statistics
type CoverageStats struct {
	EdgesCovered    int     `json:"edges_covered"`
	TotalEdges      int     `json:"total_edges"`
	HitCount        int64   `json:"hit_count"`
	NewEdges        int64   `json:"new_edges"`
	CoveragePercent float64 `json:"coverage_percent"`
}

// CoverageTracker tracks coverage across multiple executions
type CoverageTracker struct {
	globalCoverage *CoverageMap
	execCount      int64
	startTime      time.Time
	history        []CoverageSnapshot
	maxHistory     int
	mu             sync.RWMutex
}

// CoverageSnapshot represents a point-in-time coverage snapshot
type CoverageSnapshot struct {
	Timestamp     time.Time     `json:"timestamp"`
	Stats         CoverageStats `json:"stats"`
	InputHash     string        `json:"input_hash"`
	IsInteresting bool          `json:"is_interesting"`
}

// NewCoverageTracker creates a new coverage tracker
func NewCoverageTracker(bitmapSize int) *CoverageTracker {
	return &CoverageTracker{
		globalCoverage: NewCoverageMap(bitmapSize),
		startTime:      time.Now(),
		history:        make([]CoverageSnapshot, 0, 1000),
		maxHistory:     1000,
	}
}

// RecordExecution records coverage from a single execution
func (ct *CoverageTracker) RecordExecution(execCoverage *CoverageMap, inputHash string) bool {
	atomic.AddInt64(&ct.execCount, 1)

	newEdges := ct.globalCoverage.Merge(execCoverage)
	isInteresting := newEdges > 0

	ct.mu.Lock()
	defer ct.mu.Unlock()

	snapshot := CoverageSnapshot{
		Timestamp:     time.Now(),
		Stats:         ct.globalCoverage.GetStats(),
		InputHash:     inputHash,
		IsInteresting: isInteresting,
	}

	ct.history = append(ct.history, snapshot)
	if len(ct.history) > ct.maxHistory {
		ct.history = ct.history[1:]
	}

	return isInteresting
}

// GetGlobalStats returns global coverage statistics
func (ct *CoverageTracker) GetGlobalStats() CoverageStats {
	return ct.globalCoverage.GetStats()
}

// GetExecutionCount returns the number of executions
func (ct *CoverageTracker) GetExecutionCount() int64 {
	return atomic.LoadInt64(&ct.execCount)
}

// GetHistory returns the coverage history
func (ct *CoverageTracker) GetHistory() []CoverageSnapshot {
	ct.mu.RLock()
	defer ct.mu.RUnlock()

	history := make([]CoverageSnapshot, len(ct.history))
	copy(history, ct.history)
	return history
}

// GetGlobalCoverage returns the global coverage map
func (ct *CoverageTracker) GetGlobalCoverage() *CoverageMap {
	return ct.globalCoverage
}

// EdgeHasher hashes edge transitions
type EdgeHasher struct {
	lastBlock uint32
}

// NewEdgeHasher creates a new edge hasher
func NewEdgeHasher() *EdgeHasher {
	return &EdgeHasher{}
}

// HashEdge computes the edge hash for a block transition
func (eh *EdgeHasher) HashEdge(currentBlock uint32) EdgeID {
	edge := EdgeID((eh.lastBlock >> 1) ^ currentBlock)
	eh.lastBlock = currentBlock
	return edge
}

// Reset resets the edge hasher
func (eh *EdgeHasher) Reset() {
	eh.lastBlock = 0
}

// BlockID generates a block ID from a location
func BlockID(file string, line int) uint32 {
	h := sha256.New()
	h.Write([]byte(file))
	binary.Write(h, binary.LittleEndian, int32(line))
	sum := h.Sum(nil)
	return binary.LittleEndian.Uint32(sum[:4])
}
