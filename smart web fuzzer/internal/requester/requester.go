// Package requester provides the main request engine for fuzzing.
package requester

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
	"golang.org/x/time/rate"
)

// Engine orchestrates HTTP request sending with rate limiting and concurrency
type Engine struct {
	client      *Client
	pool        *WorkerPool
	limiter     *rate.Limiter
	results     chan *Result
	ctx         context.Context
	cancel      context.CancelFunc
	logger      *slog.Logger
	mu          sync.RWMutex
	isRunning   bool

	// Stats
	totalRequests   int64
	successRequests int64
	failedRequests  int64
	startTime       time.Time
}

// Result wraps a response with its original request
type Result struct {
	Request  *Request
	Response *Response
	Target   *types.FuzzTarget
}

// EngineOptions configures the request engine
type EngineOptions struct {
	Workers   int
	RPS       int
	Timeout   time.Duration
	UserAgent string
}

// DefaultEngineOptions returns sensible defaults
func DefaultEngineOptions() *EngineOptions {
	return &EngineOptions{
		Workers:   50,
		RPS:       100,
		Timeout:   10 * time.Second,
		UserAgent: "FluxFuzzer/1.0",
	}
}

// NewEngine creates a new request engine
func NewEngine(opts *EngineOptions) (*Engine, error) {
	if opts == nil {
		opts = DefaultEngineOptions()
	}

	// Create client
	client := NewClient(&ClientOptions{
		Timeout:   opts.Timeout,
		UserAgent: opts.UserAgent,
	})

	// Create worker pool
	pool, err := NewWorkerPool(&WorkerPoolOptions{
		Size: opts.Workers,
	})
	if err != nil {
		return nil, err
	}

	// Create rate limiter
	limiter := rate.NewLimiter(rate.Limit(opts.RPS), opts.RPS)

	ctx, cancel := context.WithCancel(context.Background())

	return &Engine{
		client:  client,
		pool:    pool,
		limiter: limiter,
		results: make(chan *Result, opts.Workers*2),
		ctx:     ctx,
		cancel:  cancel,
		logger:  slog.Default(),
	}, nil
}

// Start begins processing requests
func (e *Engine) Start() {
	e.mu.Lock()
	e.isRunning = true
	e.startTime = time.Now()
	e.mu.Unlock()

	e.logger.Info("Engine started",
		slog.Int("workers", e.pool.Stats().Capacity),
	)
}

// Stop gracefully stops the engine
func (e *Engine) Stop() {
	e.mu.Lock()
	e.isRunning = false
	e.mu.Unlock()

	e.cancel()
	e.pool.Shutdown()
	close(e.results)

	e.logger.Info("Engine stopped",
		slog.Int64("total_requests", e.totalRequests),
		slog.Int64("success", e.successRequests),
		slog.Int64("failed", e.failedRequests),
	)
}

// Submit sends a fuzzing target for processing
func (e *Engine) Submit(target *types.FuzzTarget) error {
	e.mu.RLock()
	if !e.isRunning {
		e.mu.RUnlock()
		return ErrEngineNotRunning
	}
	e.mu.RUnlock()

	// Wait for rate limiter
	if err := e.limiter.Wait(e.ctx); err != nil {
		return err
	}

	// Build request from target
	req := &Request{
		Method:  target.Method,
		URL:     target.URL,
		Headers: target.Headers,
		Body:    target.Body,
	}

	// Submit to worker pool
	return e.pool.Submit(func() {
		resp := e.client.Do(req)
		
		e.mu.Lock()
		e.totalRequests++
		if resp.Error == nil && resp.StatusCode < 500 {
			e.successRequests++
		} else {
			e.failedRequests++
		}
		e.mu.Unlock()

		// Send result
		select {
		case e.results <- &Result{
			Request:  req,
			Response: resp,
			Target:   target,
		}:
		case <-e.ctx.Done():
		}
	})
}

// Results returns the channel for receiving results
func (e *Engine) Results() <-chan *Result {
	return e.results
}

// Stats returns current engine statistics
type EngineStats struct {
	TotalRequests   int64
	SuccessRequests int64
	FailedRequests  int64
	RequestsPerSec  float64
	RunningWorkers  int
	Uptime          time.Duration
}

// Stats returns current statistics
func (e *Engine) Stats() EngineStats {
	e.mu.RLock()
	defer e.mu.RUnlock()

	uptime := time.Since(e.startTime)
	rps := float64(0)
	if uptime.Seconds() > 0 {
		rps = float64(e.totalRequests) / uptime.Seconds()
	}

	poolStats := e.pool.Stats()

	return EngineStats{
		TotalRequests:   e.totalRequests,
		SuccessRequests: e.successRequests,
		FailedRequests:  e.failedRequests,
		RequestsPerSec:  rps,
		RunningWorkers:  poolStats.Running,
		Uptime:          uptime,
	}
}

// Error definitions
var (
	ErrEngineNotRunning = &EngineError{Message: "engine is not running"}
)

type EngineError struct {
	Message string
}

func (e *EngineError) Error() string {
	return e.Message
}
