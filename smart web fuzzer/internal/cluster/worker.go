// Package cluster provides worker node functionality.
package cluster

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"runtime"
	"sync"
	"time"
)

// Worker represents a worker node in the cluster
type Worker struct {
	config      *ClusterConfig
	info        *NodeInfo
	client      *http.Client
	taskHandler TaskHandler
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	mu          sync.RWMutex
	running     bool
}

// TaskHandler is a function that processes a fuzz task
type TaskHandler func(ctx context.Context, task *FuzzTask) (*FuzzResult, error)

// NewWorker creates a new worker node
func NewWorker(config *ClusterConfig, handler TaskHandler) *Worker {
	if config == nil {
		config = DefaultClusterConfig()
	}
	config.Role = RoleWorker

	ctx, cancel := context.WithCancel(context.Background())

	return &Worker{
		config: config,
		info: &NodeInfo{
			ID:      config.NodeID,
			Address: config.ListenAddress,
			Role:    RoleWorker,
			Status:  StatusIdle,
		},
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		taskHandler: handler,
		ctx:         ctx,
		cancel:      cancel,
	}
}

// Start starts the worker
func (w *Worker) Start() error {
	// Register with master
	if err := w.register(); err != nil {
		return fmt.Errorf("failed to register: %w", err)
	}

	w.mu.Lock()
	w.running = true
	w.mu.Unlock()

	// Start heartbeat
	w.wg.Add(1)
	go w.heartbeat()

	// Start task processor
	w.wg.Add(1)
	go w.processTasks()

	return nil
}

// Stop stops the worker
func (w *Worker) Stop() error {
	w.mu.Lock()
	w.running = false
	w.mu.Unlock()

	w.cancel()
	w.wg.Wait()
	return nil
}

// IsRunning returns whether the worker is running
func (w *Worker) IsRunning() bool {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.running
}

// GetInfo returns worker info
func (w *Worker) GetInfo() *NodeInfo {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.info
}

// register registers with the master
func (w *Worker) register() error {
	data, err := json.Marshal(w.info)
	if err != nil {
		return err
	}

	url := fmt.Sprintf("http://%s/api/register", w.config.MasterAddress)
	resp, err := w.client.Post(url, "application/json", bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("registration failed: %d", resp.StatusCode)
	}

	return nil
}

// heartbeat sends periodic heartbeats to the master
func (w *Worker) heartbeat() {
	defer w.wg.Done()

	ticker := time.NewTicker(w.config.HeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-w.ctx.Done():
			return
		case <-ticker.C:
			w.sendHeartbeat()
		}
	}
}

// sendHeartbeat sends a heartbeat to the master
func (w *Worker) sendHeartbeat() {
	w.mu.Lock()
	w.info.LastSeen = time.Now()
	w.info.CPUUsage = getCPUUsage()
	w.info.MemUsage = getMemUsage()
	data, _ := json.Marshal(w.info)
	w.mu.Unlock()

	url := fmt.Sprintf("http://%s/api/heartbeat", w.config.MasterAddress)
	resp, err := w.client.Post(url, "application/json", bytes.NewReader(data))
	if err != nil {
		return
	}
	resp.Body.Close()
}

// processTasks fetches and processes tasks
func (w *Worker) processTasks() {
	defer w.wg.Done()

	for {
		select {
		case <-w.ctx.Done():
			return
		default:
			task, err := w.fetchTask()
			if err != nil || task == nil {
				time.Sleep(1 * time.Second)
				continue
			}

			w.setStatus(StatusWorking)
			result := w.processTask(task)
			w.submitResult(result)
			w.setStatus(StatusIdle)
		}
	}
}

// fetchTask fetches a task from the master
func (w *Worker) fetchTask() (*FuzzTask, error) {
	url := fmt.Sprintf("http://%s/api/task", w.config.MasterAddress)
	resp, err := w.client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNoContent {
		return nil, nil
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to fetch task: %d", resp.StatusCode)
	}

	var task FuzzTask
	if err := json.NewDecoder(resp.Body).Decode(&task); err != nil {
		return nil, err
	}

	return &task, nil
}

// processTask processes a single task
func (w *Worker) processTask(task *FuzzTask) *FuzzResult {
	ctx, cancel := context.WithTimeout(w.ctx, w.config.TaskTimeout)
	defer cancel()

	w.mu.Lock()
	w.info.TaskCount++
	w.mu.Unlock()

	if w.taskHandler == nil {
		return &FuzzResult{
			TaskID:  task.ID,
			Success: false,
			Error:   "no task handler configured",
		}
	}

	result, err := w.taskHandler(ctx, task)
	if err != nil {
		return &FuzzResult{
			TaskID:  task.ID,
			Success: false,
			Error:   err.Error(),
		}
	}

	result.TaskID = task.ID
	result.Success = true

	w.mu.Lock()
	w.info.ResultCount++
	w.mu.Unlock()

	return result
}

// submitResult submits a result to the master
func (w *Worker) submitResult(result *FuzzResult) error {
	data, err := json.Marshal(result)
	if err != nil {
		return err
	}

	url := fmt.Sprintf("http://%s/api/result", w.config.MasterAddress)
	resp, err := w.client.Post(url, "application/json", bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	return nil
}

// setStatus sets the worker status
func (w *Worker) setStatus(status NodeStatus) {
	w.mu.Lock()
	w.info.Status = status
	w.mu.Unlock()
}

// getCPUUsage returns current CPU usage (simplified)
func getCPUUsage() float64 {
	// Simplified - in production would use proper system metrics
	return float64(runtime.NumGoroutine()) / 100.0
}

// getMemUsage returns current memory usage
func getMemUsage() float64 {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return float64(m.Alloc) / float64(m.TotalAlloc) * 100
}
