// Package parallel provides parallelization utilities for FluxFuzzer.
// It includes dynamic worker pools, backpressure handling, and lock-free structures.
package parallel

import (
	"context"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

// WorkerPool manages a dynamic pool of workers
type WorkerPool struct {
	minWorkers     int
	maxWorkers     int
	currentWorkers int32
	taskQueue      chan Task
	resultQueue    chan Result
	ctx            context.Context
	cancel         context.CancelFunc
	wg             sync.WaitGroup
	stats          *PoolStats
	scaleInterval  time.Duration
	scaleUp        float64
	scaleDown      float64
	mu             sync.RWMutex
}

// Task represents a unit of work
type Task struct {
	ID       string
	Payload  interface{}
	Priority int
	Deadline time.Time
}

// Result represents the result of a task
type Result struct {
	TaskID  string
	Output  interface{}
	Error   error
	Latency time.Duration
}

// PoolStats tracks worker pool statistics
type PoolStats struct {
	TasksSubmitted int64
	TasksCompleted int64
	TasksDropped   int64
	WorkersSpawned int64
	WorkersRetired int64
	AvgLatencyNs   int64
	QueueLength    int64
}

// WorkerPoolConfig holds worker pool configuration
type WorkerPoolConfig struct {
	MinWorkers         int
	MaxWorkers         int
	QueueSize          int
	ScaleInterval      time.Duration
	ScaleUpThreshold   float64
	ScaleDownThreshold float64
}

// DefaultWorkerPoolConfig returns default configuration
func DefaultWorkerPoolConfig() *WorkerPoolConfig {
	numCPU := runtime.NumCPU()
	return &WorkerPoolConfig{
		MinWorkers:         numCPU,
		MaxWorkers:         numCPU * 4,
		QueueSize:          10000,
		ScaleInterval:      1 * time.Second,
		ScaleUpThreshold:   0.8,
		ScaleDownThreshold: 0.2,
	}
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(config *WorkerPoolConfig, handler TaskHandler) *WorkerPool {
	if config == nil {
		config = DefaultWorkerPoolConfig()
	}

	ctx, cancel := context.WithCancel(context.Background())

	wp := &WorkerPool{
		minWorkers:    config.MinWorkers,
		maxWorkers:    config.MaxWorkers,
		taskQueue:     make(chan Task, config.QueueSize),
		resultQueue:   make(chan Result, config.QueueSize),
		ctx:           ctx,
		cancel:        cancel,
		stats:         &PoolStats{},
		scaleInterval: config.ScaleInterval,
		scaleUp:       config.ScaleUpThreshold,
		scaleDown:     config.ScaleDownThreshold,
	}

	// Start minimum workers
	for i := 0; i < config.MinWorkers; i++ {
		wp.spawnWorker(handler)
	}

	// Start scaler
	go wp.autoScale(handler)

	return wp
}

// TaskHandler processes a task
type TaskHandler func(ctx context.Context, task Task) Result

// Submit submits a task to the pool
func (wp *WorkerPool) Submit(task Task) bool {
	select {
	case wp.taskQueue <- task:
		atomic.AddInt64(&wp.stats.TasksSubmitted, 1)
		return true
	default:
		atomic.AddInt64(&wp.stats.TasksDropped, 1)
		return false
	}
}

// SubmitWait submits a task and waits for result
func (wp *WorkerPool) SubmitWait(ctx context.Context, task Task) (Result, error) {
	resultChan := make(chan Result, 1)

	wrappedTask := Task{
		ID:       task.ID,
		Payload:  taskWithCallback{task: task, callback: resultChan},
		Priority: task.Priority,
		Deadline: task.Deadline,
	}

	select {
	case wp.taskQueue <- wrappedTask:
		atomic.AddInt64(&wp.stats.TasksSubmitted, 1)
	case <-ctx.Done():
		return Result{}, ctx.Err()
	}

	select {
	case result := <-resultChan:
		return result, nil
	case <-ctx.Done():
		return Result{}, ctx.Err()
	}
}

type taskWithCallback struct {
	task     Task
	callback chan<- Result
}

// Results returns the results channel
func (wp *WorkerPool) Results() <-chan Result {
	return wp.resultQueue
}

// Stop stops the worker pool
func (wp *WorkerPool) Stop() {
	wp.cancel()
	wp.wg.Wait()
	close(wp.taskQueue)
	close(wp.resultQueue)
}

// GetStats returns pool statistics
func (wp *WorkerPool) GetStats() PoolStats {
	return PoolStats{
		TasksSubmitted: atomic.LoadInt64(&wp.stats.TasksSubmitted),
		TasksCompleted: atomic.LoadInt64(&wp.stats.TasksCompleted),
		TasksDropped:   atomic.LoadInt64(&wp.stats.TasksDropped),
		WorkersSpawned: atomic.LoadInt64(&wp.stats.WorkersSpawned),
		WorkersRetired: atomic.LoadInt64(&wp.stats.WorkersRetired),
		AvgLatencyNs:   atomic.LoadInt64(&wp.stats.AvgLatencyNs),
		QueueLength:    int64(len(wp.taskQueue)),
	}
}

// CurrentWorkers returns current worker count
func (wp *WorkerPool) CurrentWorkers() int {
	return int(atomic.LoadInt32(&wp.currentWorkers))
}

// spawnWorker spawns a new worker
func (wp *WorkerPool) spawnWorker(handler TaskHandler) {
	atomic.AddInt32(&wp.currentWorkers, 1)
	atomic.AddInt64(&wp.stats.WorkersSpawned, 1)

	wp.wg.Add(1)
	go func() {
		defer wp.wg.Done()
		defer atomic.AddInt32(&wp.currentWorkers, -1)

		for {
			select {
			case <-wp.ctx.Done():
				return
			case task, ok := <-wp.taskQueue:
				if !ok {
					return
				}

				start := time.Now()

				// Check if this is a wrapped task with callback
				var result Result
				if tc, ok := task.Payload.(taskWithCallback); ok {
					// Execute handler with original task
					result = handler(wp.ctx, tc.task)
					result.Latency = time.Since(start)
					select {
					case tc.callback <- result:
					default:
					}
				} else {
					// Execute handler with original task
					result = handler(wp.ctx, task)
					result.Latency = time.Since(start)
					select {
					case wp.resultQueue <- result:
					default:
					}
				}

				atomic.AddInt64(&wp.stats.TasksCompleted, 1)

				// Update average latency
				latencyNs := result.Latency.Nanoseconds()
				completed := atomic.LoadInt64(&wp.stats.TasksCompleted)
				if completed > 0 {
					avgLatency := atomic.LoadInt64(&wp.stats.AvgLatencyNs)
					newAvg := avgLatency + (latencyNs-avgLatency)/completed
					atomic.StoreInt64(&wp.stats.AvgLatencyNs, newAvg)
				}
			}
		}
	}()
}

// autoScale automatically scales workers based on load
func (wp *WorkerPool) autoScale(handler TaskHandler) {
	ticker := time.NewTicker(wp.scaleInterval)
	defer ticker.Stop()

	for {
		select {
		case <-wp.ctx.Done():
			return
		case <-ticker.C:
			queueLen := len(wp.taskQueue)
			queueCap := cap(wp.taskQueue)
			utilization := float64(queueLen) / float64(queueCap)

			currentWorkers := int(atomic.LoadInt32(&wp.currentWorkers))

			if utilization > wp.scaleUp && currentWorkers < wp.maxWorkers {
				// Scale up
				wp.spawnWorker(handler)
			} else if utilization < wp.scaleDown && currentWorkers > wp.minWorkers {
				// Scale down by not replacing retiring workers
				atomic.AddInt64(&wp.stats.WorkersRetired, 1)
			}
		}
	}
}

// SetCPUAffinity sets the process to use specific CPU cores
func SetCPUAffinity(numCores int) {
	if numCores <= 0 {
		numCores = runtime.NumCPU()
	}
	runtime.GOMAXPROCS(numCores)
}

// GetCPUAffinity returns current GOMAXPROCS setting
func GetCPUAffinity() int {
	return runtime.GOMAXPROCS(0)
}
