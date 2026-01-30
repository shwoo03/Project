package parallel

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestWorkerPool(t *testing.T) {
	config := &WorkerPoolConfig{
		MinWorkers:    2,
		MaxWorkers:    4,
		QueueSize:     100,
		ScaleInterval: 100 * time.Millisecond,
	}

	handler := func(ctx context.Context, task Task) Result {
		time.Sleep(10 * time.Millisecond)
		return Result{
			TaskID: task.ID,
			Output: task.Payload,
		}
	}

	pool := NewWorkerPool(config, handler)
	defer pool.Stop()

	// Submit tasks
	for i := 0; i < 10; i++ {
		task := Task{
			ID:      string(rune('A' + i)),
			Payload: i,
		}
		if !pool.Submit(task) {
			t.Error("Failed to submit task")
		}
	}

	// Wait for results
	time.Sleep(200 * time.Millisecond)

	stats := pool.GetStats()
	if stats.TasksSubmitted != 10 {
		t.Errorf("Expected 10 submitted, got %d", stats.TasksSubmitted)
	}
	if stats.TasksCompleted < 5 {
		t.Errorf("Expected at least 5 completed, got %d", stats.TasksCompleted)
	}
}

func TestWorkerPoolSubmitWait(t *testing.T) {
	handler := func(ctx context.Context, task Task) Result {
		return Result{
			TaskID: task.ID,
			Output: task.Payload.(int) * 2,
		}
	}

	pool := NewWorkerPool(nil, handler)
	defer pool.Stop()

	ctx := context.Background()
	task := Task{
		ID:      "test-1",
		Payload: 21,
	}

	result, err := pool.SubmitWait(ctx, task)
	if err != nil {
		t.Fatalf("SubmitWait failed: %v", err)
	}

	if result.Output != 42 {
		t.Errorf("Expected 42, got %v", result.Output)
	}
}

func TestWorkerPoolAutoScale(t *testing.T) {
	config := &WorkerPoolConfig{
		MinWorkers:         1,
		MaxWorkers:         4,
		QueueSize:          100,
		ScaleInterval:      50 * time.Millisecond,
		ScaleUpThreshold:   0.3,
		ScaleDownThreshold: 0.1,
	}

	handler := func(ctx context.Context, task Task) Result {
		time.Sleep(50 * time.Millisecond)
		return Result{TaskID: task.ID}
	}

	pool := NewWorkerPool(config, handler)
	defer pool.Stop()

	// Submit many tasks to trigger scaling
	for i := 0; i < 50; i++ {
		pool.Submit(Task{ID: string(rune(i))})
	}

	// Wait for auto-scaling
	time.Sleep(200 * time.Millisecond)

	workers := pool.CurrentWorkers()
	t.Logf("Current workers: %d", workers)
}

func TestBackpressureController(t *testing.T) {
	config := &BackpressureConfig{
		Strategy:      StrategyAdaptive,
		MaxQueueSize:  100,
		HighWatermark: 0.8,
		LowWatermark:  0.2,
		MinRate:       1 * time.Millisecond,
		MaxRate:       10 * time.Millisecond,
	}

	bc := NewBackpressureController(config)

	// Low pressure
	canProceed := bc.CheckPressure(10, 100) // 10%
	if !canProceed {
		t.Error("Should proceed at low pressure")
	}
	if bc.IsPressured() {
		t.Error("Should not be pressured at 10%")
	}

	// High pressure
	canProceed = bc.CheckPressure(90, 100) // 90%
	if !canProceed {
		t.Error("Adaptive strategy should allow proceeding")
	}
	if !bc.IsPressured() {
		t.Error("Should be pressured at 90%")
	}

	stats := bc.GetStats()
	if stats.PressureEvents != 1 {
		t.Errorf("Expected 1 pressure event, got %d", stats.PressureEvents)
	}
}

func TestRateLimiter(t *testing.T) {
	rl := NewRateLimiter(10*time.Millisecond, 3)

	// Burst should allow 3 immediate requests
	for i := 0; i < 3; i++ {
		if !rl.Allow() {
			t.Errorf("Request %d should be allowed (burst)", i)
		}
	}

	// 4th request should be denied
	if rl.Allow() {
		t.Error("4th request should be denied")
	}

	// Wait and try again
	time.Sleep(15 * time.Millisecond)
	if !rl.Allow() {
		t.Error("Request after wait should be allowed")
	}
}

func TestThrottle(t *testing.T) {
	throttle := NewThrottle(50 * time.Millisecond)

	// First call should be allowed
	if !throttle.Allow() {
		t.Error("First call should be allowed")
	}

	// Immediate second call should be denied
	if throttle.Allow() {
		t.Error("Immediate second call should be denied")
	}

	// Wait and try again
	time.Sleep(60 * time.Millisecond)
	if !throttle.Allow() {
		t.Error("Call after wait should be allowed")
	}
}

func TestLockFreeQueue(t *testing.T) {
	queue := NewLockFreeQueue()

	// Test empty queue
	if !queue.IsEmpty() {
		t.Error("New queue should be empty")
	}

	// Enqueue items
	for i := 0; i < 10; i++ {
		queue.Enqueue(i)
	}

	if queue.Len() != 10 {
		t.Errorf("Expected len 10, got %d", queue.Len())
	}

	// Dequeue items
	for i := 0; i < 10; i++ {
		value, ok := queue.Dequeue()
		if !ok {
			t.Error("Dequeue should succeed")
		}
		if value.(int) != i {
			t.Errorf("Expected %d, got %d", i, value.(int))
		}
	}

	if !queue.IsEmpty() {
		t.Error("Queue should be empty after dequeue all")
	}
}

func TestLockFreeQueueConcurrent(t *testing.T) {
	queue := NewLockFreeQueue()
	var wg sync.WaitGroup
	numGoroutines := 10
	numItems := 100

	// Concurrent enqueue
	wg.Add(numGoroutines)
	for i := 0; i < numGoroutines; i++ {
		go func(id int) {
			defer wg.Done()
			for j := 0; j < numItems; j++ {
				queue.Enqueue(id*1000 + j)
			}
		}(i)
	}
	wg.Wait()

	expectedLen := int64(numGoroutines * numItems)
	if queue.Len() != expectedLen {
		t.Errorf("Expected len %d, got %d", expectedLen, queue.Len())
	}

	// Concurrent dequeue
	var dequeued int64
	wg.Add(numGoroutines)
	for i := 0; i < numGoroutines; i++ {
		go func() {
			defer wg.Done()
			for {
				if _, ok := queue.Dequeue(); ok {
					atomic.AddInt64(&dequeued, 1)
				} else {
					break
				}
			}
		}()
	}
	wg.Wait()

	if dequeued != expectedLen {
		t.Errorf("Expected to dequeue %d, got %d", expectedLen, dequeued)
	}
}

func TestLockFreeStack(t *testing.T) {
	stack := NewLockFreeStack()

	// Push items (LIFO order)
	for i := 0; i < 5; i++ {
		stack.Push(i)
	}

	if stack.Len() != 5 {
		t.Errorf("Expected len 5, got %d", stack.Len())
	}

	// Pop should return in reverse order
	for i := 4; i >= 0; i-- {
		value, ok := stack.Pop()
		if !ok {
			t.Error("Pop should succeed")
		}
		if value.(int) != i {
			t.Errorf("Expected %d, got %d", i, value.(int))
		}
	}
}

func TestAtomicCounter(t *testing.T) {
	counter := NewAtomicCounter(0)

	// Increment
	for i := 0; i < 100; i++ {
		counter.Inc()
	}
	if counter.Get() != 100 {
		t.Errorf("Expected 100, got %d", counter.Get())
	}

	// Decrement
	counter.Dec()
	if counter.Get() != 99 {
		t.Errorf("Expected 99, got %d", counter.Get())
	}

	// CAS
	if !counter.CompareAndSwap(99, 200) {
		t.Error("CAS should succeed")
	}
	if counter.Get() != 200 {
		t.Errorf("Expected 200, got %d", counter.Get())
	}
}

func TestAtomicFlag(t *testing.T) {
	flag := NewAtomicFlag(false)

	if flag.IsSet() {
		t.Error("Flag should not be set")
	}

	flag.Set()
	if !flag.IsSet() {
		t.Error("Flag should be set")
	}

	flag.Clear()
	if flag.IsSet() {
		t.Error("Flag should not be set after clear")
	}

	// Toggle
	result := flag.Toggle()
	if !result || !flag.IsSet() {
		t.Error("Toggle should set flag")
	}
}

func TestCPUAffinity(t *testing.T) {
	original := GetCPUAffinity()

	SetCPUAffinity(2)
	if GetCPUAffinity() != 2 {
		t.Errorf("Expected 2, got %d", GetCPUAffinity())
	}

	// Restore
	SetCPUAffinity(original)
}

func BenchmarkLockFreeQueue(b *testing.B) {
	queue := NewLockFreeQueue()

	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			if i%2 == 0 {
				queue.Enqueue(i)
			} else {
				queue.Dequeue()
			}
			i++
		}
	})
}

func BenchmarkLockFreeStack(b *testing.B) {
	stack := NewLockFreeStack()

	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			if i%2 == 0 {
				stack.Push(i)
			} else {
				stack.Pop()
			}
			i++
		}
	})
}
