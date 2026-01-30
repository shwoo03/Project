// Package coverage provides corpus management for coverage-guided fuzzing.
package coverage

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

// Corpus manages test inputs for fuzzing
type Corpus struct {
	entries    []*CorpusEntry
	crashes    []*CrashEntry
	entryIndex map[string]*CorpusEntry
	dir        string
	mu         sync.RWMutex
}

// CorpusEntry represents a single corpus entry
type CorpusEntry struct {
	Data           []byte        `json:"-"`
	Hash           string        `json:"hash"`
	Size           int           `json:"size"`
	Coverage       CoverageStats `json:"coverage"`
	DiscoveredAt   time.Time     `json:"discovered_at"`
	ExecutionCount int64         `json:"execution_count"`
	IsSeed         bool          `json:"is_seed"`
	Favored        bool          `json:"favored"`
}

// CrashEntry represents a crash-inducing input
type CrashEntry struct {
	Input        []byte    `json:"-"`
	Hash         string    `json:"hash"`
	Output       []byte    `json:"-"`
	ExitCode     int       `json:"exit_code"`
	DiscoveredAt time.Time `json:"discovered_at"`
	Unique       bool      `json:"unique"`
}

// NewCorpus creates a new corpus
func NewCorpus(dir string) *Corpus {
	if dir == "" {
		dir = filepath.Join(os.TempDir(), "fluxfuzzer_corpus")
	}

	os.MkdirAll(dir, 0755)
	os.MkdirAll(filepath.Join(dir, "queue"), 0755)
	os.MkdirAll(filepath.Join(dir, "crashes"), 0755)

	return &Corpus{
		entries:    make([]*CorpusEntry, 0),
		crashes:    make([]*CrashEntry, 0),
		entryIndex: make(map[string]*CorpusEntry),
		dir:        dir,
	}
}

// Add adds an entry to the corpus
func (c *Corpus) Add(entry *CorpusEntry) bool {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Check for duplicates
	if _, exists := c.entryIndex[entry.Hash]; exists {
		return false
	}

	entry.Size = len(entry.Data)
	c.entries = append(c.entries, entry)
	c.entryIndex[entry.Hash] = entry

	// Save to disk
	c.saveEntry(entry)

	return true
}

// AddCrash adds a crash-inducing input
func (c *Corpus) AddCrash(input []byte, result *ExecutionResult) bool {
	c.mu.Lock()
	defer c.mu.Unlock()

	hash := hashBytes(input)

	// Check for duplicate crashes
	for _, crash := range c.crashes {
		if crash.Hash == hash {
			return false
		}
	}

	crash := &CrashEntry{
		Input:        input,
		Hash:         hash,
		Output:       result.Output,
		ExitCode:     result.ExitCode,
		DiscoveredAt: time.Now(),
		Unique:       true,
	}

	c.crashes = append(c.crashes, crash)

	// Save crash to disk
	c.saveCrash(crash)

	return true
}

// GetEntries returns all corpus entries
func (c *Corpus) GetEntries() []*CorpusEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entries := make([]*CorpusEntry, len(c.entries))
	copy(entries, c.entries)
	return entries
}

// GetEntry returns an entry by hash
func (c *Corpus) GetEntry(hash string) *CorpusEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.entryIndex[hash]
}

// GetCrashes returns all crash entries
func (c *Corpus) GetCrashes() []*CrashEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	crashes := make([]*CrashEntry, len(c.crashes))
	copy(crashes, c.crashes)
	return crashes
}

// Size returns the number of entries
func (c *Corpus) Size() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.entries)
}

// CrashCount returns the number of crashes
func (c *Corpus) CrashCount() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.crashes)
}

// GetFavored returns favored entries
func (c *Corpus) GetFavored() []*CorpusEntry {
	c.mu.RLock()
	defer c.mu.RUnlock()

	var favored []*CorpusEntry
	for _, e := range c.entries {
		if e.Favored {
			favored = append(favored, e)
		}
	}
	return favored
}

// Minimize minimizes the corpus by removing redundant entries
func (c *Corpus) Minimize() int {
	c.mu.Lock()
	defer c.mu.Unlock()

	if len(c.entries) <= 1 {
		return 0
	}

	// Sort by coverage (descending)
	sort.Slice(c.entries, func(i, j int) bool {
		return c.entries[i].Coverage.EdgesCovered > c.entries[j].Coverage.EdgesCovered
	})

	// Mark first entry as favored
	c.entries[0].Favored = true

	// Simple greedy minimization
	removed := 0
	coveredEdges := make(map[int]bool)

	// Keep entries that contribute unique edges
	var kept []*CorpusEntry
	for _, entry := range c.entries {
		// Check if this entry contributes unique coverage
		contributes := false
		if entry.Coverage.EdgesCovered > 0 {
			// Simplified check - in reality would need edge-level tracking
			contributes = true
		}

		if contributes || entry.IsSeed || entry.Favored {
			kept = append(kept, entry)
		} else {
			removed++
			delete(c.entryIndex, entry.Hash)
		}
	}

	c.entries = kept
	_ = coveredEdges // Used for edge tracking

	return removed
}

// saveEntry saves an entry to disk
func (c *Corpus) saveEntry(entry *CorpusEntry) error {
	// Save input data
	inputPath := filepath.Join(c.dir, "queue", entry.Hash)
	if err := os.WriteFile(inputPath, entry.Data, 0644); err != nil {
		return err
	}

	// Save metadata
	metaPath := filepath.Join(c.dir, "queue", entry.Hash+".json")
	meta, _ := json.Marshal(entry)
	return os.WriteFile(metaPath, meta, 0644)
}

// saveCrash saves a crash to disk
func (c *Corpus) saveCrash(crash *CrashEntry) error {
	// Save input
	inputPath := filepath.Join(c.dir, "crashes", crash.Hash)
	if err := os.WriteFile(inputPath, crash.Input, 0644); err != nil {
		return err
	}

	// Save output
	if len(crash.Output) > 0 {
		outputPath := filepath.Join(c.dir, "crashes", crash.Hash+".output")
		os.WriteFile(outputPath, crash.Output, 0644)
	}

	// Save metadata
	metaPath := filepath.Join(c.dir, "crashes", crash.Hash+".json")
	meta, _ := json.Marshal(crash)
	return os.WriteFile(metaPath, meta, 0644)
}

// Load loads the corpus from disk
func (c *Corpus) Load() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Load queue
	queueDir := filepath.Join(c.dir, "queue")
	files, err := os.ReadDir(queueDir)
	if err != nil {
		return err
	}

	for _, file := range files {
		if filepath.Ext(file.Name()) == ".json" {
			continue
		}

		data, err := os.ReadFile(filepath.Join(queueDir, file.Name()))
		if err != nil {
			continue
		}

		entry := &CorpusEntry{
			Data: data,
			Hash: file.Name(),
			Size: len(data),
		}

		// Try to load metadata
		metaPath := filepath.Join(queueDir, file.Name()+".json")
		if metaData, err := os.ReadFile(metaPath); err == nil {
			json.Unmarshal(metaData, entry)
		}

		c.entries = append(c.entries, entry)
		c.entryIndex[entry.Hash] = entry
	}

	return nil
}

// GetStats returns corpus statistics
func (c *Corpus) GetStats() CorpusStats {
	c.mu.RLock()
	defer c.mu.RUnlock()

	totalSize := 0
	maxSize := 0
	minSize := 0
	favored := 0
	seeds := 0

	for i, e := range c.entries {
		totalSize += e.Size
		if e.Size > maxSize {
			maxSize = e.Size
		}
		if i == 0 || e.Size < minSize {
			minSize = e.Size
		}
		if e.Favored {
			favored++
		}
		if e.IsSeed {
			seeds++
		}
	}

	avgSize := 0
	if len(c.entries) > 0 {
		avgSize = totalSize / len(c.entries)
	}

	return CorpusStats{
		EntryCount:  len(c.entries),
		CrashCount:  len(c.crashes),
		TotalSize:   totalSize,
		AverageSize: avgSize,
		MaxSize:     maxSize,
		MinSize:     minSize,
		Favored:     favored,
		Seeds:       seeds,
	}
}

// CorpusStats holds corpus statistics
type CorpusStats struct {
	EntryCount  int `json:"entry_count"`
	CrashCount  int `json:"crash_count"`
	TotalSize   int `json:"total_size"`
	AverageSize int `json:"average_size"`
	MaxSize     int `json:"max_size"`
	MinSize     int `json:"min_size"`
	Favored     int `json:"favored"`
	Seeds       int `json:"seeds"`
}

// hashBytes generates a hash for bytes
func hashBytes(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

// CorpusPruner periodically prunes the corpus
type CorpusPruner struct {
	corpus   *Corpus
	interval time.Duration
	stopCh   chan struct{}
}

// NewCorpusPruner creates a new corpus pruner
func NewCorpusPruner(corpus *Corpus, interval time.Duration) *CorpusPruner {
	return &CorpusPruner{
		corpus:   corpus,
		interval: interval,
		stopCh:   make(chan struct{}),
	}
}

// Start starts the pruner
func (cp *CorpusPruner) Start() {
	go func() {
		ticker := time.NewTicker(cp.interval)
		defer ticker.Stop()

		for {
			select {
			case <-cp.stopCh:
				return
			case <-ticker.C:
				cp.corpus.Minimize()
			}
		}
	}()
}

// Stop stops the pruner
func (cp *CorpusPruner) Stop() {
	close(cp.stopCh)
}
