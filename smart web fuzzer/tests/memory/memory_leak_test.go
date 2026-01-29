// Package memory provides memory leak detection tests for FluxFuzzer.
package memory

import (
	"net/http"
	"net/http/httptest"
	"runtime"
	"sync"
	"testing"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/requester"
)

// MemoryCheckpoint represents a memory state snapshot
type MemoryCheckpoint struct {
	Name      string
	HeapAlloc uint64
	HeapSys   uint64
	NumGC     uint32
}

// captureMemory forces GC and captures memory stats
func captureMemory(name string) MemoryCheckpoint {
	// Force garbage collection to get accurate readings
	runtime.GC()
	runtime.GC() // Second GC for finalizers

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	return MemoryCheckpoint{
		Name:      name,
		HeapAlloc: m.HeapAlloc,
		HeapSys:   m.HeapSys,
		NumGC:     m.NumGC,
	}
}

// TestMemoryLeak_WorkerPool tests for memory leaks in worker pool
func TestMemoryLeak_WorkerPool(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping memory leak test in short mode")
	}

	baseline := captureMemory("baseline")
	t.Logf("Baseline: HeapAlloc=%.2f MB, HeapSys=%.2f MB",
		float64(baseline.HeapAlloc)/1024/1024, float64(baseline.HeapSys)/1024/1024)

	iterations := 10
	tasksPerIteration := 10000

	for i := 0; i < iterations; i++ {
		pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
			Size:        100,
			PreAlloc:    true,
			MaxBlocking: 1000,
		})
		if err != nil {
			t.Fatalf("failed to create worker pool: %v", err)
		}

		var wg sync.WaitGroup
		for j := 0; j < tasksPerIteration; j++ {
			wg.Add(1)
			_ = pool.Submit(func() {
				defer wg.Done()
				// Simulate some work
				time.Sleep(100 * time.Microsecond)
			})
		}
		wg.Wait()
		pool.Shutdown()

		if i%3 == 0 {
			checkpoint := captureMemory("iteration")
			t.Logf("Iteration %d: HeapAlloc=%.2f MB", i, float64(checkpoint.HeapAlloc)/1024/1024)
		}
	}

	// Allow time for cleanup
	time.Sleep(100 * time.Millisecond)
	final := captureMemory("final")

	t.Logf("Final: HeapAlloc=%.2f MB, HeapSys=%.2f MB",
		float64(final.HeapAlloc)/1024/1024, float64(final.HeapSys)/1024/1024)

	// Check for significant memory growth (more than 50MB growth is suspicious)
	growth := int64(final.HeapAlloc) - int64(baseline.HeapAlloc)
	growthMB := float64(growth) / 1024 / 1024
	t.Logf("Memory growth: %.2f MB", growthMB)

	if growthMB > 50 {
		t.Errorf("Suspected memory leak: %.2f MB growth after %d iterations", growthMB, iterations)
	}
}

// TestMemoryLeak_HTTPClient tests for memory leaks in HTTP client
func TestMemoryLeak_HTTPClient(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping memory leak test in short mode")
	}

	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status": "ok", "data": "test response body with some content"}`))
	}))
	defer server.Close()

	baseline := captureMemory("baseline")
	t.Logf("Baseline: HeapAlloc=%.2f MB", float64(baseline.HeapAlloc)/1024/1024)

	iterations := 5
	requestsPerIteration := 5000

	for i := 0; i < iterations; i++ {
		client := requester.NewClient(&requester.ClientOptions{
			Timeout:             5 * time.Second,
			MaxConnsPerHost:     100,
			MaxIdleConnDuration: 10 * time.Second,
			UserAgent:           "FluxFuzzer-MemTest/1.0",
			SkipTLSVerify:       true,
		})

		pool, _ := requester.NewWorkerPool(&requester.WorkerPoolOptions{
			Size:        100,
			PreAlloc:    true,
			MaxBlocking: 500,
		})

		var wg sync.WaitGroup
		for j := 0; j < requestsPerIteration; j++ {
			wg.Add(1)
			_ = pool.Submit(func() {
				defer wg.Done()
				req := &requester.Request{
					Method: "GET",
					URL:    server.URL,
				}
				resp := client.Do(req)
				_ = resp // Use response to prevent optimization
			})
		}
		wg.Wait()
		pool.Shutdown()

		checkpoint := captureMemory("iteration")
		t.Logf("Iteration %d: HeapAlloc=%.2f MB, Requests=%d",
			i+1, float64(checkpoint.HeapAlloc)/1024/1024, requestsPerIteration)
	}

	// Allow time for cleanup
	time.Sleep(200 * time.Millisecond)
	final := captureMemory("final")

	t.Logf("Final: HeapAlloc=%.2f MB", float64(final.HeapAlloc)/1024/1024)

	growth := int64(final.HeapAlloc) - int64(baseline.HeapAlloc)
	growthMB := float64(growth) / 1024 / 1024
	t.Logf("Memory growth: %.2f MB", growthMB)

	if growthMB > 100 {
		t.Errorf("Suspected memory leak: %.2f MB growth after %d total requests",
			growthMB, iterations*requestsPerIteration)
	}
}

// TestMemoryLeak_ResponseBody tests for memory leaks in response body handling
func TestMemoryLeak_ResponseBody(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping memory leak test in short mode")
	}

	// Create test server with large response
	largeBody := make([]byte, 10*1024) // 10KB response
	for i := range largeBody {
		largeBody[i] = byte('A' + (i % 26))
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write(largeBody)
	}))
	defer server.Close()

	baseline := captureMemory("baseline")
	t.Logf("Baseline: HeapAlloc=%.2f MB", float64(baseline.HeapAlloc)/1024/1024)

	client := requester.NewClient(requester.DefaultClientOptions())
	pool, _ := requester.NewWorkerPool(requester.DefaultWorkerPoolOptions())
	defer pool.Shutdown()

	// Send many requests with large responses
	requests := 10000
	var wg sync.WaitGroup
	for i := 0; i < requests; i++ {
		wg.Add(1)
		_ = pool.Submit(func() {
			defer wg.Done()
			req := &requester.Request{
				Method: "GET",
				URL:    server.URL,
			}
			resp := client.Do(req)
			if resp.Error == nil {
				// Verify body is copied correctly
				_ = len(resp.Body)
			}
		})
	}
	wg.Wait()

	// Check memory at peak
	peak := captureMemory("peak")
	t.Logf("Peak: HeapAlloc=%.2f MB", float64(peak.HeapAlloc)/1024/1024)

	// Allow cleanup
	time.Sleep(500 * time.Millisecond)
	final := captureMemory("final")

	t.Logf("Final: HeapAlloc=%.2f MB", float64(final.HeapAlloc)/1024/1024)

	// Check that memory released after requests complete (should be close to baseline)
	retained := int64(final.HeapAlloc) - int64(baseline.HeapAlloc)
	retainedMB := float64(retained) / 1024 / 1024
	t.Logf("Retained memory: %.2f MB", retainedMB)

	// Expected: ~10KB * 10000 = 100MB at peak, should release most after completion
	if retainedMB > 50 {
		t.Errorf("Memory not properly released: %.2f MB retained", retainedMB)
	}
}

// TestMemoryLeak_ConcurrentCreation tests for leaks when creating/destroying many pools
func TestMemoryLeak_ConcurrentCreation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping memory leak test in short mode")
	}

	baseline := captureMemory("baseline")
	t.Logf("Baseline: HeapAlloc=%.2f MB", float64(baseline.HeapAlloc)/1024/1024)

	iterations := 50

	for i := 0; i < iterations; i++ {
		// Create multiple pools concurrently
		var wg sync.WaitGroup
		pools := make([]*requester.WorkerPool, 10)

		for j := 0; j < 10; j++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
					Size:        50,
					PreAlloc:    true,
					MaxBlocking: 500,
				})
				if err != nil {
					return
				}
				pools[idx] = pool

				// Submit some tasks
				for k := 0; k < 100; k++ {
					_ = pool.Submit(func() {
						time.Sleep(1 * time.Millisecond)
					})
				}
			}(j)
		}
		wg.Wait()

		// Shutdown all pools
		for _, pool := range pools {
			if pool != nil {
				pool.Wait()
				pool.Shutdown()
			}
		}
	}

	// Allow cleanup
	time.Sleep(500 * time.Millisecond)
	final := captureMemory("final")

	t.Logf("Final: HeapAlloc=%.2f MB", float64(final.HeapAlloc)/1024/1024)

	growth := int64(final.HeapAlloc) - int64(baseline.HeapAlloc)
	growthMB := float64(growth) / 1024 / 1024
	t.Logf("Memory growth: %.2f MB after %d iterations", growthMB, iterations)

	if growthMB > 30 {
		t.Errorf("Suspected goroutine/memory leak: %.2f MB growth", growthMB)
	}
}
