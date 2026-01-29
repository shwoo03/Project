// Package requester provides worker pool management for concurrent requests.
package requester

import (
	"sync"
	"sync/atomic"

	"github.com/panjf2000/ants/v2"
)

// WorkerPool manages a pool of goroutines for concurrent request processing
type WorkerPool struct {
	pool       *ants.Pool
	wg         sync.WaitGroup
	isShutdown atomic.Bool
	
	// Metrics
	submitted  atomic.Int64
	completed  atomic.Int64
	errors     atomic.Int64
}

// WorkerPoolOptions configures the worker pool
type WorkerPoolOptions struct {
	Size       int
	PreAlloc   bool
	MaxBlocking int
}

// DefaultWorkerPoolOptions returns sensible defaults
func DefaultWorkerPoolOptions() *WorkerPoolOptions {
	return &WorkerPoolOptions{
		Size:       100,
		PreAlloc:   true,
		MaxBlocking: 1000,
	}
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(opts *WorkerPoolOptions) (*WorkerPool, error) {
	if opts == nil {
		opts = DefaultWorkerPoolOptions()
	}

	pool, err := ants.NewPool(
		opts.Size,
		ants.WithPreAlloc(opts.PreAlloc),
		ants.WithMaxBlockingTasks(opts.MaxBlocking),
	)
	if err != nil {
		return nil, err
	}

	return &WorkerPool{
		pool: pool,
	}, nil
}

// Submit adds a task to the worker pool
func (wp *WorkerPool) Submit(task func()) error {
	if wp.isShutdown.Load() {
		return ants.ErrPoolClosed
	}

	wp.submitted.Add(1)
	wp.wg.Add(1)

	return wp.pool.Submit(func() {
		defer wp.wg.Done()
		defer wp.completed.Add(1)
		task()
	})
}

// SubmitWithError adds a task that can return an error
func (wp *WorkerPool) SubmitWithError(task func() error) error {
	return wp.Submit(func() {
		if err := task(); err != nil {
			wp.errors.Add(1)
		}
	})
}

// Wait blocks until all submitted tasks complete
func (wp *WorkerPool) Wait() {
	wp.wg.Wait()
}

// Shutdown gracefully shuts down the worker pool
func (wp *WorkerPool) Shutdown() {
	wp.isShutdown.Store(true)
	wp.Wait()
	wp.pool.Release()
}

// Stats returns the current pool statistics
type PoolStats struct {
	Running   int
	Capacity  int
	Submitted int64
	Completed int64
	Errors    int64
}

// Stats returns current worker pool statistics
func (wp *WorkerPool) Stats() PoolStats {
	return PoolStats{
		Running:   wp.pool.Running(),
		Capacity:  wp.pool.Cap(),
		Submitted: wp.submitted.Load(),
		Completed: wp.completed.Load(),
		Errors:    wp.errors.Load(),
	}
}

// Tune dynamically adjusts the pool size
func (wp *WorkerPool) Tune(size int) {
	wp.pool.Tune(size)
}
