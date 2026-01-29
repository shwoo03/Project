// Package benchmark provides performance benchmarks for FluxFuzzer components.
package benchmark

import (
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/requester"
)

// BenchmarkClientDo benchmarks the HTTP client performance
func BenchmarkClientDo(b *testing.B) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status": "ok"}`))
	}))
	defer server.Close()

	client := requester.NewClient(requester.DefaultClientOptions())

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			req := &requester.Request{
				Method: "GET",
				URL:    server.URL,
			}
			resp := client.Do(req)
			if resp.Error != nil {
				b.Errorf("request failed: %v", resp.Error)
			}
		}
	})
}

// BenchmarkWorkerPoolSubmit benchmarks worker pool task submission
func BenchmarkWorkerPoolSubmit(b *testing.B) {
	pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
		Size:        100,
		PreAlloc:    true,
		MaxBlocking: 1000,
	})
	if err != nil {
		b.Fatalf("failed to create worker pool: %v", err)
	}
	defer pool.Shutdown()

	var counter atomic.Int64

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = pool.Submit(func() {
			counter.Add(1)
			time.Sleep(10 * time.Microsecond) // Simulate minimal work
		})
	}
	pool.Wait()
}

// BenchmarkWorkerPoolWithHTTP benchmarks worker pool with actual HTTP requests
func BenchmarkWorkerPoolWithHTTP(b *testing.B) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status": "ok"}`))
	}))
	defer server.Close()

	pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
		Size:        100,
		PreAlloc:    true,
		MaxBlocking: 1000,
	})
	if err != nil {
		b.Fatalf("failed to create worker pool: %v", err)
	}
	defer pool.Shutdown()

	client := requester.NewClient(requester.DefaultClientOptions())

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = pool.Submit(func() {
			req := &requester.Request{
				Method: "GET",
				URL:    server.URL,
			}
			client.Do(req)
		})
	}
	pool.Wait()
}

// BenchmarkRPSThroughput measures actual RPS throughput
func BenchmarkRPSThroughput(b *testing.B) {
	// Create test server with minimal response
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
		Size:        500,
		PreAlloc:    true,
		MaxBlocking: 5000,
	})
	if err != nil {
		b.Fatalf("failed to create worker pool: %v", err)
	}
	defer pool.Shutdown()

	client := requester.NewClient(&requester.ClientOptions{
		Timeout:             5 * time.Second,
		MaxConnsPerHost:     500,
		MaxIdleConnDuration: 10 * time.Second,
		UserAgent:           "FluxFuzzer-Benchmark/1.0",
		SkipTLSVerify:       true,
	})

	start := time.Now()
	requestCount := 10000
	var completed atomic.Int64

	b.ResetTimer()
	for i := 0; i < requestCount; i++ {
		_ = pool.Submit(func() {
			req := &requester.Request{
				Method: "GET",
				URL:    server.URL,
			}
			resp := client.Do(req)
			if resp.Error == nil {
				completed.Add(1)
			}
		})
	}
	pool.Wait()

	elapsed := time.Since(start)
	rps := float64(completed.Load()) / elapsed.Seconds()
	b.ReportMetric(rps, "requests/sec")
}

// TestTargetRPS validates that we can achieve target RPS
func TestTargetRPS(t *testing.T) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status": "ok"}`))
	}))
	defer server.Close()

	targetRPS := 1000
	testDuration := 5 * time.Second

	pool, err := requester.NewWorkerPool(&requester.WorkerPoolOptions{
		Size:        200,
		PreAlloc:    true,
		MaxBlocking: 2000,
	})
	if err != nil {
		t.Fatalf("failed to create worker pool: %v", err)
	}
	defer pool.Shutdown()

	client := requester.NewClient(requester.DefaultClientOptions())

	var completed atomic.Int64
	var failed atomic.Int64
	var wg sync.WaitGroup

	start := time.Now()
	ticker := time.NewTicker(time.Second / time.Duration(targetRPS))
	defer ticker.Stop()

	done := make(chan struct{})
	go func() {
		time.Sleep(testDuration)
		close(done)
	}()

	// Send requests at target rate
	for {
		select {
		case <-done:
			goto finish
		case <-ticker.C:
			wg.Add(1)
			_ = pool.Submit(func() {
				defer wg.Done()
				req := &requester.Request{
					Method: "GET",
					URL:    server.URL,
				}
				resp := client.Do(req)
				if resp.Error == nil && resp.StatusCode == 200 {
					completed.Add(1)
				} else {
					failed.Add(1)
				}
			})
		}
	}

finish:
	wg.Wait()
	pool.Wait()

	elapsed := time.Since(start)
	actualRPS := float64(completed.Load()) / elapsed.Seconds()

	t.Logf("Test Duration: %v", elapsed)
	t.Logf("Completed Requests: %d", completed.Load())
	t.Logf("Failed Requests: %d", failed.Load())
	t.Logf("Actual RPS: %.2f", actualRPS)
	t.Logf("Target RPS: %d", targetRPS)

	// Allow 80% of target as minimum acceptable
	minAcceptableRPS := float64(targetRPS) * 0.8
	if actualRPS < minAcceptableRPS {
		t.Errorf("RPS below target: got %.2f, want at least %.2f", actualRPS, minAcceptableRPS)
	}
}
