package cluster

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestNewCoordinator(t *testing.T) {
	c := NewCoordinator(nil)
	if c == nil {
		t.Fatal("NewCoordinator returned nil")
	}

	if c.config.Role != RoleMaster {
		t.Errorf("Expected role Master, got %s", c.config.Role)
	}
}

func TestCoordinatorAddTask(t *testing.T) {
	c := NewCoordinator(nil)

	task := &FuzzTask{
		ID:     "test-1",
		URL:    "http://example.com",
		Method: "GET",
	}

	c.AddTask(task)

	stats := c.GetStats()
	if stats.TotalTasks != 1 {
		t.Errorf("Expected 1 task, got %d", stats.TotalTasks)
	}
}

func TestCoordinatorAPI(t *testing.T) {
	config := &ClusterConfig{
		ListenAddress: ":0", // Use random port
		NodeID:        "test-master",
	}
	c := NewCoordinator(config)

	// Test registration handler
	t.Run("Register", func(t *testing.T) {
		node := NodeInfo{
			ID:      "worker-1",
			Address: "localhost:9001",
			Role:    RoleWorker,
		}
		body, _ := json.Marshal(node)

		req := httptest.NewRequest("POST", "/api/register", bytesReader(body))
		w := httptest.NewRecorder()

		c.handleRegister(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}

		workers := c.GetWorkers()
		if len(workers) != 1 {
			t.Errorf("Expected 1 worker, got %d", len(workers))
		}
	})

	// Test heartbeat handler
	t.Run("Heartbeat", func(t *testing.T) {
		node := NodeInfo{
			ID:     "worker-1",
			Status: StatusWorking,
		}
		body, _ := json.Marshal(node)

		req := httptest.NewRequest("POST", "/api/heartbeat", bytesReader(body))
		w := httptest.NewRecorder()

		c.handleHeartbeat(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}
	})

	// Test stats handler
	t.Run("Stats", func(t *testing.T) {
		req := httptest.NewRequest("GET", "/api/stats", nil)
		w := httptest.NewRecorder()

		c.handleStats(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}
	})
}

func TestNewWorker(t *testing.T) {
	handler := func(ctx context.Context, task *FuzzTask) (*FuzzResult, error) {
		return &FuzzResult{TaskID: task.ID, Success: true}, nil
	}

	w := NewWorker(nil, handler)
	if w == nil {
		t.Fatal("NewWorker returned nil")
	}

	if w.config.Role != RoleWorker {
		t.Errorf("Expected role Worker, got %s", w.config.Role)
	}
}

func TestTaskQueue(t *testing.T) {
	q := NewTaskQueue()

	// Add tasks with different priorities
	q.Add(&FuzzTask{ID: "low", Priority: 1})
	q.Add(&FuzzTask{ID: "high", Priority: 10})
	q.Add(&FuzzTask{ID: "medium", Priority: 5})

	if q.Len() != 3 {
		t.Errorf("Expected 3 tasks, got %d", q.Len())
	}

	// Pop should return highest priority first
	task := q.Pop()
	if task.ID != "high" {
		t.Errorf("Expected 'high', got '%s'", task.ID)
	}

	task = q.Pop()
	if task.ID != "medium" {
		t.Errorf("Expected 'medium', got '%s'", task.ID)
	}

	task = q.Pop()
	if task.ID != "low" {
		t.Errorf("Expected 'low', got '%s'", task.ID)
	}

	// Queue should be empty
	if q.Len() != 0 {
		t.Errorf("Expected 0 tasks, got %d", q.Len())
	}
}

func TestTaskGenerator(t *testing.T) {
	gen := NewTaskGenerator()

	// Test GenerateFromURL
	payloads := []string{"payload1", "payload2", "payload3"}
	tasks := gen.GenerateFromURL("http://example.com", "POST", payloads)

	if len(tasks) != 3 {
		t.Errorf("Expected 3 tasks, got %d", len(tasks))
	}

	for i, task := range tasks {
		if task.URL != "http://example.com" {
			t.Errorf("Task %d: wrong URL", i)
		}
		if task.Method != "POST" {
			t.Errorf("Task %d: wrong method", i)
		}
		if task.Type != TaskTypeFuzz {
			t.Errorf("Task %d: wrong type", i)
		}
	}

	// Test GenerateCrawlTask
	crawlTask := gen.GenerateCrawlTask("http://example.com")
	if crawlTask.Type != TaskTypeCrawl {
		t.Errorf("Expected crawl type, got %s", crawlTask.Type)
	}
	if crawlTask.Priority != 10 {
		t.Errorf("Expected priority 10, got %d", crawlTask.Priority)
	}

	// Test GenerateVerifyTask
	original := &FuzzTask{
		ID:     "original-1",
		URL:    "http://example.com/api",
		Method: "POST",
	}
	verifyTask := gen.GenerateVerifyTask(original, "test-payload")
	if verifyTask.Type != TaskTypeVerify {
		t.Errorf("Expected verify type, got %s", verifyTask.Type)
	}
	if verifyTask.Metadata["original_task_id"] != "original-1" {
		t.Error("Missing original_task_id in metadata")
	}
}

func TestClusterIntegration(t *testing.T) {
	// Start coordinator server
	coordConfig := &ClusterConfig{
		ListenAddress:     ":0",
		NodeID:            "master-test",
		HeartbeatInterval: 100 * time.Millisecond,
	}
	coord := NewCoordinator(coordConfig)

	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/register":
			coord.handleRegister(w, r)
		case "/api/heartbeat":
			coord.handleHeartbeat(w, r)
		case "/api/task":
			coord.handleGetTask(w, r)
		case "/api/result":
			coord.handleSubmitResult(w, r)
		case "/api/stats":
			coord.handleStats(w, r)
		}
	}))
	defer server.Close()

	// Add some tasks
	gen := NewTaskGenerator()
	tasks := gen.GenerateFromURL("http://target.com/api", "GET", []string{"test1", "test2"})
	coord.AddTasks(tasks)

	stats := coord.GetStats()
	if stats.TotalTasks != 2 {
		t.Errorf("Expected 2 tasks, got %d", stats.TotalTasks)
	}

	t.Log("Cluster integration test passed")
}

// Helper
func bytesReader(data []byte) *bytesBuffer {
	return &bytesBuffer{data: data}
}

type bytesBuffer struct {
	data []byte
	pos  int
}

func (b *bytesBuffer) Read(p []byte) (n int, err error) {
	if b.pos >= len(b.data) {
		return 0, nil
	}
	n = copy(p, b.data[b.pos:])
	b.pos += n
	return n, nil
}
