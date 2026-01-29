// Package stability provides long-running stability tests for FluxFuzzer.
package stability

import (
	"context"
	"net/http"
	"net/http/httptest"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/requester"
)

// StabilityConfig holds configuration for stability tests
type StabilityConfig struct {
	Duration       time.Duration
	TargetRPS      int
	WorkerPoolSize int
	MaxBlocking    int
}

// DefaultStabilityConfig returns default stability test configuration
func DefaultStabilityConfig() StabilityConfig {
	return StabilityConfig{
		Duration:       10 * time.Minute, // Short version for CI
		TargetRPS:      500,
		WorkerPoolSize: 100,
		MaxBlocking:    1000,
	}
}

// FullStabilityConfig returns 1-hour stability test configuration
func FullStabilityConfig() StabilityConfig {
	return StabilityConfig{
		Duration:       1 * time.Hour,
		TargetRPS:      1000,
		WorkerPoolSize: 200,
		MaxBlocking:    2000,
	}
}

// StabilityMetrics tracks metrics during stability test
type StabilityMetrics struct {
	TotalRequests   atomic.Int64
	SuccessRequests atomic.Int64
	FailedRequests  atomic.Int64
	TotalLatencyNs  atomic.Int64
	MaxLatencyNs    atomic.Int64
	MinLatencyNs    atomic.Int64

	// Memory metrics (sampled periodically)
	MemorySamples []MemorySample
	mu            sync.Mutex
}

// MemorySample represents a memory snapshot
type MemorySample struct {
	Timestamp  time.Time
	Alloc      uint64
	TotalAlloc uint64
	Sys        uint64
	HeapAlloc  uint64
	HeapSys    uint64
	HeapIdle   uint64
	HeapInuse  uint64
	NumGC      uint32
}

// RecordRequest records a request result
func (m *StabilityMetrics) RecordRequest(success bool, latency time.Duration) {
	m.TotalRequests.Add(1)
	latencyNs := latency.Nanoseconds()
	m.TotalLatencyNs.Add(latencyNs)

	// Update max latency (atomic compare-and-swap loop)
	for {
		current := m.MaxLatencyNs.Load()
		if latencyNs <= current {
			break
		}
		if m.MaxLatencyNs.CompareAndSwap(current, latencyNs) {
			break
		}
	}

	// Update min latency (atomic compare-and-swap loop)
	for {
		current := m.MinLatencyNs.Load()
		if current != 0 && latencyNs >= current {
			break
		}
		if m.MinLatencyNs.CompareAndSwap(current, latencyNs) {
			break
		}
	}

	if success {
		m.SuccessRequests.Add(1)
	} else {
		m.FailedRequests.Add(1)
	}
}

// SampleMemory takes a memory sample
func (m *StabilityMetrics) SampleMemory() {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	sample := MemorySample{
		Timestamp:  time.Now(),
		Alloc:      memStats.Alloc,
		TotalAlloc: memStats.TotalAlloc,
		Sys:        memStats.Sys,
		HeapAlloc:  memStats.HeapAlloc,
		HeapSys:    memStats.HeapSys,
		HeapIdle:   memStats.HeapIdle,
		HeapInuse:  memStats.HeapInuse,
		NumGC:      memStats.NumGC,
	}

	m.mu.Lock()
	m.MemorySamples = append(m.MemorySamples, sample)
	m.mu.Unlock()
}

// Summary returns a summary of stability metrics
func (m *StabilityMetrics) Summary() StabilitySummary {
	total := m.TotalRequests.Load()
	success := m.SuccessRequests.Load()
	failed := m.FailedRequests.Load()
	totalLatency := m.TotalLatencyNs.Load()

	var avgLatency time.Duration
	if total > 0 {
		avgLatency = time.Duration(totalLatency / total)
	}

	m.mu.Lock()
	samples := m.MemorySamples
	m.mu.Unlock()

	var maxHeap, minHeap, avgHeap uint64
	if len(samples) > 0 {
		minHeap = samples[0].HeapAlloc
		var totalHeap uint64
		for _, s := range samples {
			if s.HeapAlloc > maxHeap {
				maxHeap = s.HeapAlloc
			}
			if s.HeapAlloc < minHeap {
				minHeap = s.HeapAlloc
			}
			totalHeap += s.HeapAlloc
		}
		avgHeap = totalHeap / uint64(len(samples))
	}

	return StabilitySummary{
		TotalRequests:   total,
		SuccessRequests: success,
		FailedRequests:  failed,
		SuccessRate:     float64(success) / float64(total) * 100,
		AvgLatency:      avgLatency,
		MaxLatency:      time.Duration(m.MaxLatencyNs.Load()),
		MinLatency:      time.Duration(m.MinLatencyNs.Load()),
		MaxHeapMB:       float64(maxHeap) / 1024 / 1024,
		MinHeapMB:       float64(minHeap) / 1024 / 1024,
		AvgHeapMB:       float64(avgHeap) / 1024 / 1024,
		MemorySamples:   len(samples),
	}
}

// StabilitySummary holds summarized stability metrics
type StabilitySummary struct {
	TotalRequests   int64
	SuccessRequests int64
	FailedRequests  int64
	SuccessRate     float64
	AvgLatency      time.Duration
	MaxLatency      time.Duration
	MinLatency      time.Duration
	MaxHeapMB       float64
	MinHeapMB       float64
	AvgHeapMB       float64
	MemorySamples   int
}

// TestStability_Short runs a 10-minute stability test
func TestStability_Short(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping stability test in short mode")
	}

	config := StabilityConfig{
		Duration:       10 * time.Minute,
		TargetRPS:      500,
		WorkerPoolSize: 100,
		MaxBlocking:    1000,
	}

	runStabilityTest(t, config)
}

// TestStability_Full runs a 1-hour stability test
func TestStability_Full(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping full stability test in short mode")
	}

	// Check for explicit enable flag
	if !testing.Verbose() {
		t.Skip("Run with -v flag to enable full 1-hour stability test")
	}

	runStabilityTest(t, FullStabilityConfig())
}

// runStabilityTest executes a stability test with the given configuration
func runStabilityTest(t *testing.T, config StabilityConfig) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status": "ok"}`))
	}))
	defer server.Close()

	// Create worker pool
	pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
		Size:        config.WorkerPoolSize,
		PreAlloc:    true,
		MaxBlocking: config.MaxBlocking,
	})
	if err != nil {
		t.Fatalf("failed to create worker pool: %v", err)
	}
	defer pool.Shutdown()

	// Create HTTP client
	client := requester.NewClient(&requester.ClientOptions{
		Timeout:             10 * time.Second,
		MaxConnsPerHost:     500,
		MaxIdleConnDuration: 30 * time.Second,
		UserAgent:           "FluxFuzzer-Stability/1.0",
		SkipTLSVerify:       true,
	})

	metrics := &StabilityMetrics{}

	// Context for test duration
	ctx, cancel := context.WithTimeout(context.Background(), config.Duration)
	defer cancel()

	// Start memory sampler
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				metrics.SampleMemory()
			}
		}
	}()

	// Progress reporter
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		start := time.Now()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				elapsed := time.Since(start)
				total := metrics.TotalRequests.Load()
				rps := float64(total) / elapsed.Seconds()
				t.Logf("Progress: %v elapsed, %d requests, %.2f RPS", elapsed.Round(time.Second), total, rps)
			}
		}
	}()

	// Request sender
	ticker := time.NewTicker(time.Second / time.Duration(config.TargetRPS))
	defer ticker.Stop()

	t.Logf("Starting stability test: %v duration, %d target RPS", config.Duration, config.TargetRPS)

	for {
		select {
		case <-ctx.Done():
			goto finish
		case <-ticker.C:
			_ = pool.Submit(func() {
				start := time.Now()
				req := &requester.Request{
					Method: "GET",
					URL:    server.URL,
				}
				resp := client.Do(req)
				latency := time.Since(start)
				success := resp.Error == nil && resp.StatusCode == 200
				metrics.RecordRequest(success, latency)
			})
		}
	}

finish:
	pool.Wait()
	metrics.SampleMemory() // Final sample

	// Report results
	summary := metrics.Summary()
	t.Logf("\n=== Stability Test Results ===")
	t.Logf("Duration: %v", config.Duration)
	t.Logf("Total Requests: %d", summary.TotalRequests)
	t.Logf("Successful: %d", summary.SuccessRequests)
	t.Logf("Failed: %d", summary.FailedRequests)
	t.Logf("Success Rate: %.2f%%", summary.SuccessRate)
	t.Logf("Avg Latency: %v", summary.AvgLatency)
	t.Logf("Max Latency: %v", summary.MaxLatency)
	t.Logf("Min Latency: %v", summary.MinLatency)
	t.Logf("Actual RPS: %.2f", float64(summary.TotalRequests)/config.Duration.Seconds())
	t.Logf("\n=== Memory Metrics ===")
	t.Logf("Min Heap: %.2f MB", summary.MinHeapMB)
	t.Logf("Max Heap: %.2f MB", summary.MaxHeapMB)
	t.Logf("Avg Heap: %.2f MB", summary.AvgHeapMB)
	t.Logf("Memory Samples: %d", summary.MemorySamples)

	// Assertions
	if summary.SuccessRate < 99.0 {
		t.Errorf("Success rate too low: %.2f%% (expected >= 99%%)", summary.SuccessRate)
	}

	// Check for memory growth (last sample should not be more than 2x first sample)
	if len(metrics.MemorySamples) > 10 {
		first := metrics.MemorySamples[0].HeapAlloc
		last := metrics.MemorySamples[len(metrics.MemorySamples)-1].HeapAlloc
		ratio := float64(last) / float64(first)
		t.Logf("Memory growth ratio: %.2fx", ratio)
		if ratio > 2.0 {
			t.Errorf("Potential memory leak detected: heap grew from %.2f MB to %.2f MB (%.2fx)",
				float64(first)/1024/1024, float64(last)/1024/1024, ratio)
		}
	}
}
