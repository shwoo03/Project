// Package coverage provides feedback loop for coverage-guided fuzzing.
package coverage

import (
	"context"
	"crypto/sha256"
	"math"
	"sync"
	"sync/atomic"
	"time"
)

// FeedbackLoop implements the coverage-guided feedback loop
type FeedbackLoop struct {
	tracker   *CoverageTracker
	corpus    *Corpus
	scheduler *InputScheduler
	mutator   InputMutator
	executor  Executor
	config    *FeedbackConfig
	stats     *FeedbackStats
	running   int32
	stopCh    chan struct{}
	mu        sync.RWMutex
}

// FeedbackConfig holds feedback loop configuration
type FeedbackConfig struct {
	MaxExecutions    int64
	Timeout          time.Duration
	BitmapSize       int
	CorpusDir        string
	MutationsPerSeed int
	MaxInputSize     int
	MinInputSize     int
}

// DefaultFeedbackConfig returns default configuration
func DefaultFeedbackConfig() *FeedbackConfig {
	return &FeedbackConfig{
		MaxExecutions:    1000000,
		Timeout:          1 * time.Hour,
		BitmapSize:       65536,
		MutationsPerSeed: 10,
		MaxInputSize:     1 << 20, // 1MB
		MinInputSize:     1,
	}
}

// FeedbackStats holds feedback loop statistics
type FeedbackStats struct {
	Executions          int64     `json:"executions"`
	InterestingInputs   int64     `json:"interesting_inputs"`
	CrasheS             int64     `json:"crashes"`
	Timeouts            int64     `json:"timeouts"`
	AvgExecTimeNs       int64     `json:"avg_exec_time_ns"`
	ExecsPerSec         float64   `json:"execs_per_sec"`
	CoveragePercent     float64   `json:"coverage_percent"`
	StartTime           time.Time `json:"start_time"`
	LastInterestingTime time.Time `json:"last_interesting_time"`
}

// InputMutator mutates inputs
type InputMutator interface {
	Mutate(input []byte) []byte
}

// Executor executes an input and returns coverage
type Executor interface {
	Execute(ctx context.Context, input []byte) (*ExecutionResult, error)
}

// ExecutionResult holds the result of an execution
type ExecutionResult struct {
	Coverage *CoverageMap
	Output   []byte
	ExitCode int
	Crashed  bool
	TimedOut bool
	Duration time.Duration
}

// NewFeedbackLoop creates a new feedback loop
func NewFeedbackLoop(config *FeedbackConfig, mutator InputMutator, executor Executor) *FeedbackLoop {
	if config == nil {
		config = DefaultFeedbackConfig()
	}

	return &FeedbackLoop{
		tracker:   NewCoverageTracker(config.BitmapSize),
		corpus:    NewCorpus(config.CorpusDir),
		scheduler: NewInputScheduler(),
		mutator:   mutator,
		executor:  executor,
		config:    config,
		stats:     &FeedbackStats{StartTime: time.Now()},
		stopCh:    make(chan struct{}),
	}
}

// Start starts the feedback loop
func (fl *FeedbackLoop) Start(ctx context.Context) error {
	if !atomic.CompareAndSwapInt32(&fl.running, 0, 1) {
		return nil // Already running
	}

	go fl.run(ctx)
	return nil
}

// Stop stops the feedback loop
func (fl *FeedbackLoop) Stop() {
	if atomic.CompareAndSwapInt32(&fl.running, 1, 0) {
		close(fl.stopCh)
	}
}

// run is the main fuzzing loop
func (fl *FeedbackLoop) run(ctx context.Context) {
	startTime := time.Now()

	for {
		select {
		case <-ctx.Done():
			return
		case <-fl.stopCh:
			return
		default:
		}

		// Check termination conditions
		execCount := atomic.LoadInt64(&fl.stats.Executions)
		if execCount >= fl.config.MaxExecutions {
			return
		}
		if time.Since(startTime) > fl.config.Timeout {
			return
		}

		// Get next input from scheduler
		input := fl.scheduler.Next(fl.corpus)
		if input == nil {
			// No inputs, use empty
			input = &CorpusEntry{Data: []byte{}}
		}

		// Mutate and execute
		for i := 0; i < fl.config.MutationsPerSeed; i++ {
			mutated := fl.mutator.Mutate(input.Data)
			if len(mutated) > fl.config.MaxInputSize {
				mutated = mutated[:fl.config.MaxInputSize]
			}

			fl.executeAndRecord(ctx, mutated)
		}
	}
}

// executeAndRecord executes an input and records results
func (fl *FeedbackLoop) executeAndRecord(ctx context.Context, input []byte) {
	execStart := time.Now()
	result, err := fl.executor.Execute(ctx, input)
	execDuration := time.Since(execStart)

	atomic.AddInt64(&fl.stats.Executions, 1)

	if err != nil || result == nil {
		return
	}

	// Update execution time average
	execNs := execDuration.Nanoseconds()
	execCount := atomic.LoadInt64(&fl.stats.Executions)
	if execCount > 0 {
		avgNs := atomic.LoadInt64(&fl.stats.AvgExecTimeNs)
		newAvg := avgNs + (execNs-avgNs)/execCount
		atomic.StoreInt64(&fl.stats.AvgExecTimeNs, newAvg)
	}

	// Handle crashes
	if result.Crashed {
		atomic.AddInt64(&fl.stats.CrasheS, 1)
		fl.corpus.AddCrash(input, result)
	}

	// Handle timeouts
	if result.TimedOut {
		atomic.AddInt64(&fl.stats.Timeouts, 1)
	}

	// Check for new coverage
	if result.Coverage != nil {
		inputHash := hashInput(input)
		isInteresting := fl.tracker.RecordExecution(result.Coverage, inputHash)

		if isInteresting {
			atomic.AddInt64(&fl.stats.InterestingInputs, 1)
			fl.stats.LastInterestingTime = time.Now()

			// Add to corpus
			entry := &CorpusEntry{
				Data:         input,
				Hash:         inputHash,
				Coverage:     result.Coverage.GetStats(),
				DiscoveredAt: time.Now(),
			}
			fl.corpus.Add(entry)
			fl.scheduler.UpdatePriority(entry)
		}
	}

	// Update coverage stats
	fl.mu.Lock()
	fl.stats.CoveragePercent = fl.tracker.GetGlobalStats().CoveragePercent
	elapsed := time.Since(fl.stats.StartTime).Seconds()
	if elapsed > 0 {
		fl.stats.ExecsPerSec = float64(atomic.LoadInt64(&fl.stats.Executions)) / elapsed
	}
	fl.mu.Unlock()
}

// GetStats returns current statistics
func (fl *FeedbackLoop) GetStats() FeedbackStats {
	fl.mu.RLock()
	defer fl.mu.RUnlock()

	return FeedbackStats{
		Executions:          atomic.LoadInt64(&fl.stats.Executions),
		InterestingInputs:   atomic.LoadInt64(&fl.stats.InterestingInputs),
		CrasheS:             atomic.LoadInt64(&fl.stats.CrasheS),
		Timeouts:            atomic.LoadInt64(&fl.stats.Timeouts),
		AvgExecTimeNs:       atomic.LoadInt64(&fl.stats.AvgExecTimeNs),
		ExecsPerSec:         fl.stats.ExecsPerSec,
		CoveragePercent:     fl.stats.CoveragePercent,
		StartTime:           fl.stats.StartTime,
		LastInterestingTime: fl.stats.LastInterestingTime,
	}
}

// GetTracker returns the coverage tracker
func (fl *FeedbackLoop) GetTracker() *CoverageTracker {
	return fl.tracker
}

// GetCorpus returns the corpus
func (fl *FeedbackLoop) GetCorpus() *Corpus {
	return fl.corpus
}

// AddSeed adds a seed input to the corpus
func (fl *FeedbackLoop) AddSeed(input []byte) {
	entry := &CorpusEntry{
		Data:         input,
		Hash:         hashInput(input),
		DiscoveredAt: time.Now(),
		IsSeed:       true,
	}
	fl.corpus.Add(entry)
}

// InputScheduler schedules inputs based on priority
type InputScheduler struct {
	weights map[string]float64
	mu      sync.RWMutex
}

// NewInputScheduler creates a new input scheduler
func NewInputScheduler() *InputScheduler {
	return &InputScheduler{
		weights: make(map[string]float64),
	}
}

// Next returns the next input to fuzz
func (is *InputScheduler) Next(corpus *Corpus) *CorpusEntry {
	entries := corpus.GetEntries()
	if len(entries) == 0 {
		return nil
	}

	is.mu.RLock()
	defer is.mu.RUnlock()

	// Weighted random selection
	totalWeight := 0.0
	for _, e := range entries {
		w := is.weights[e.Hash]
		if w <= 0 {
			w = 1.0
		}
		totalWeight += w
	}

	// Simple round-robin for now
	// Could implement more sophisticated scheduling
	return entries[time.Now().UnixNano()%int64(len(entries))]
}

// UpdatePriority updates the priority of an input
func (is *InputScheduler) UpdatePriority(entry *CorpusEntry) {
	is.mu.Lock()
	defer is.mu.Unlock()

	// Higher priority for entries with more coverage
	weight := 1.0
	if entry.Coverage.EdgesCovered > 0 {
		weight = math.Log2(float64(entry.Coverage.EdgesCovered) + 1)
	}

	is.weights[entry.Hash] = weight
}

// hashInput generates a hash for an input
func hashInput(input []byte) string {
	return ContentHash(input)
}

// ContentHash generates a hex-encoded SHA256 hash
func ContentHash(data []byte) string {
	h := sha256.Sum256(data)
	result := make([]byte, 64)
	for i, b := range h {
		result[i*2] = "0123456789abcdef"[b>>4]
		result[i*2+1] = "0123456789abcdef"[b&0x0f]
	}
	return string(result)
}
