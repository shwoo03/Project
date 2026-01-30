// Package cluster provides distributed fuzzing capabilities.
// It supports master-worker architecture for scaling fuzzing across multiple nodes.
package cluster

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

// NodeRole represents the role of a cluster node
type NodeRole string

const (
	RoleMaster NodeRole = "master"
	RoleWorker NodeRole = "worker"
)

// NodeStatus represents the status of a node
type NodeStatus string

const (
	StatusIdle    NodeStatus = "idle"
	StatusWorking NodeStatus = "working"
	StatusPaused  NodeStatus = "paused"
	StatusOffline NodeStatus = "offline"
	StatusError   NodeStatus = "error"
)

// NodeInfo contains information about a cluster node
type NodeInfo struct {
	ID          string     `json:"id"`
	Address     string     `json:"address"`
	Role        NodeRole   `json:"role"`
	Status      NodeStatus `json:"status"`
	LastSeen    time.Time  `json:"last_seen"`
	TaskCount   int        `json:"task_count"`
	ResultCount int        `json:"result_count"`
	CPUUsage    float64    `json:"cpu_usage"`
	MemUsage    float64    `json:"mem_usage"`
}

// ClusterConfig holds cluster configuration
type ClusterConfig struct {
	MasterAddress     string        `json:"master_address"`
	ListenAddress     string        `json:"listen_address"`
	NodeID            string        `json:"node_id"`
	Role              NodeRole      `json:"role"`
	HeartbeatInterval time.Duration `json:"heartbeat_interval"`
	TaskTimeout       time.Duration `json:"task_timeout"`
	MaxRetries        int           `json:"max_retries"`
}

// DefaultClusterConfig returns a default configuration
func DefaultClusterConfig() *ClusterConfig {
	return &ClusterConfig{
		MasterAddress:     "localhost:9000",
		ListenAddress:     ":9001",
		NodeID:            generateNodeID(),
		Role:              RoleWorker,
		HeartbeatInterval: 5 * time.Second,
		TaskTimeout:       30 * time.Second,
		MaxRetries:        3,
	}
}

// Coordinator manages the distributed fuzzing cluster (Master node)
type Coordinator struct {
	config    *ClusterConfig
	workers   map[string]*NodeInfo
	taskQueue chan *FuzzTask
	results   chan *FuzzResult
	mu        sync.RWMutex
	ctx       context.Context
	cancel    context.CancelFunc
	server    *http.Server
	stats     *ClusterStats
}

// ClusterStats holds cluster-wide statistics
type ClusterStats struct {
	TotalTasks     int64     `json:"total_tasks"`
	CompletedTasks int64     `json:"completed_tasks"`
	FailedTasks    int64     `json:"failed_tasks"`
	TotalResults   int64     `json:"total_results"`
	AnomaliesFound int64     `json:"anomalies_found"`
	ActiveWorkers  int       `json:"active_workers"`
	StartTime      time.Time `json:"start_time"`
	mu             sync.RWMutex
}

// NewCoordinator creates a new cluster coordinator
func NewCoordinator(config *ClusterConfig) *Coordinator {
	if config == nil {
		config = DefaultClusterConfig()
	}
	config.Role = RoleMaster

	ctx, cancel := context.WithCancel(context.Background())

	return &Coordinator{
		config:    config,
		workers:   make(map[string]*NodeInfo),
		taskQueue: make(chan *FuzzTask, 10000),
		results:   make(chan *FuzzResult, 10000),
		ctx:       ctx,
		cancel:    cancel,
		stats: &ClusterStats{
			StartTime: time.Now(),
		},
	}
}

// Start starts the coordinator
func (c *Coordinator) Start() error {
	mux := http.NewServeMux()

	// API endpoints
	mux.HandleFunc("/api/register", c.handleRegister)
	mux.HandleFunc("/api/heartbeat", c.handleHeartbeat)
	mux.HandleFunc("/api/task", c.handleGetTask)
	mux.HandleFunc("/api/result", c.handleSubmitResult)
	mux.HandleFunc("/api/stats", c.handleStats)
	mux.HandleFunc("/api/workers", c.handleWorkers)

	c.server = &http.Server{
		Addr:    c.config.ListenAddress,
		Handler: mux,
	}

	// Start worker monitor
	go c.monitorWorkers()

	// Start result collector
	go c.collectResults()

	return c.server.ListenAndServe()
}

// Stop stops the coordinator
func (c *Coordinator) Stop() error {
	c.cancel()
	if c.server != nil {
		return c.server.Shutdown(context.Background())
	}
	return nil
}

// AddTask adds a task to the queue
func (c *Coordinator) AddTask(task *FuzzTask) {
	select {
	case c.taskQueue <- task:
		c.stats.mu.Lock()
		c.stats.TotalTasks++
		c.stats.mu.Unlock()
	default:
		// Queue full
	}
}

// AddTasks adds multiple tasks to the queue
func (c *Coordinator) AddTasks(tasks []*FuzzTask) {
	for _, task := range tasks {
		c.AddTask(task)
	}
}

// GetResults returns the results channel
func (c *Coordinator) GetResults() <-chan *FuzzResult {
	return c.results
}

// GetStats returns current cluster statistics
func (c *Coordinator) GetStats() *ClusterStats {
	c.stats.mu.RLock()
	defer c.stats.mu.RUnlock()

	c.mu.RLock()
	activeWorkers := 0
	for _, w := range c.workers {
		if w.Status == StatusWorking || w.Status == StatusIdle {
			activeWorkers++
		}
	}
	c.mu.RUnlock()

	c.stats.ActiveWorkers = activeWorkers
	return c.stats
}

// GetWorkers returns list of workers
func (c *Coordinator) GetWorkers() []*NodeInfo {
	c.mu.RLock()
	defer c.mu.RUnlock()

	workers := make([]*NodeInfo, 0, len(c.workers))
	for _, w := range c.workers {
		workers = append(workers, w)
	}
	return workers
}

// handleRegister handles worker registration
func (c *Coordinator) handleRegister(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var node NodeInfo
	if err := json.NewDecoder(r.Body).Decode(&node); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	node.LastSeen = time.Now()
	node.Status = StatusIdle

	c.mu.Lock()
	c.workers[node.ID] = &node
	c.mu.Unlock()

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "registered"})
}

// handleHeartbeat handles worker heartbeat
func (c *Coordinator) handleHeartbeat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var node NodeInfo
	if err := json.NewDecoder(r.Body).Decode(&node); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	c.mu.Lock()
	if existing, ok := c.workers[node.ID]; ok {
		existing.LastSeen = time.Now()
		existing.Status = node.Status
		existing.TaskCount = node.TaskCount
		existing.ResultCount = node.ResultCount
		existing.CPUUsage = node.CPUUsage
		existing.MemUsage = node.MemUsage
	}
	c.mu.Unlock()

	w.WriteHeader(http.StatusOK)
}

// handleGetTask handles task requests from workers
func (c *Coordinator) handleGetTask(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	select {
	case task := <-c.taskQueue:
		json.NewEncoder(w).Encode(task)
	case <-time.After(5 * time.Second):
		w.WriteHeader(http.StatusNoContent)
	}
}

// handleSubmitResult handles result submissions from workers
func (c *Coordinator) handleSubmitResult(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var result FuzzResult
	if err := json.NewDecoder(r.Body).Decode(&result); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	select {
	case c.results <- &result:
		c.stats.mu.Lock()
		c.stats.TotalResults++
		if result.Success {
			c.stats.CompletedTasks++
		} else {
			c.stats.FailedTasks++
		}
		if len(result.Anomalies) > 0 {
			c.stats.AnomaliesFound += int64(len(result.Anomalies))
		}
		c.stats.mu.Unlock()
	default:
	}

	w.WriteHeader(http.StatusOK)
}

// handleStats handles stats requests
func (c *Coordinator) handleStats(w http.ResponseWriter, r *http.Request) {
	stats := c.GetStats()
	json.NewEncoder(w).Encode(stats)
}

// handleWorkers handles workers list requests
func (c *Coordinator) handleWorkers(w http.ResponseWriter, r *http.Request) {
	workers := c.GetWorkers()
	json.NewEncoder(w).Encode(workers)
}

// monitorWorkers monitors worker health
func (c *Coordinator) monitorWorkers() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-c.ctx.Done():
			return
		case <-ticker.C:
			c.mu.Lock()
			for id, worker := range c.workers {
				if time.Since(worker.LastSeen) > 30*time.Second {
					worker.Status = StatusOffline
				}
				_ = id // silence unused variable warning
			}
			c.mu.Unlock()
		}
	}
}

// collectResults collects and processes results
func (c *Coordinator) collectResults() {
	for {
		select {
		case <-c.ctx.Done():
			return
		case result := <-c.results:
			// Process result (e.g., store in database, notify)
			_ = result
		}
	}
}

// generateNodeID generates a unique node ID
func generateNodeID() string {
	return fmt.Sprintf("node-%d", time.Now().UnixNano())
}
