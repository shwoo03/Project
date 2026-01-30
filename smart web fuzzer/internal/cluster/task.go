// Package cluster provides task and result types.
package cluster

import (
	"fmt"
	"time"
)

// FuzzTask represents a fuzzing task
type FuzzTask struct {
	ID          string            `json:"id"`
	Type        TaskType          `json:"type"`
	URL         string            `json:"url"`
	Method      string            `json:"method"`
	Headers     map[string]string `json:"headers,omitempty"`
	Body        []byte            `json:"body,omitempty"`
	Payloads    []string          `json:"payloads,omitempty"`
	MutatorType string            `json:"mutator_type,omitempty"`
	Priority    int               `json:"priority"`
	Retries     int               `json:"retries"`
	MaxRetries  int               `json:"max_retries"`
	Timeout     time.Duration     `json:"timeout"`
	CreatedAt   time.Time         `json:"created_at"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// TaskType represents the type of fuzzing task
type TaskType string

const (
	TaskTypeScan   TaskType = "scan"   // Initial scanning
	TaskTypeFuzz   TaskType = "fuzz"   // Active fuzzing
	TaskTypeVerify TaskType = "verify" // Verification
	TaskTypeCrawl  TaskType = "crawl"  // Crawling
	TaskTypeReplay TaskType = "replay" // Replay request
)

// FuzzResult represents the result of a fuzzing task
type FuzzResult struct {
	TaskID       string        `json:"task_id"`
	WorkerID     string        `json:"worker_id"`
	Success      bool          `json:"success"`
	Error        string        `json:"error,omitempty"`
	StatusCode   int           `json:"status_code"`
	ResponseTime time.Duration `json:"response_time"`
	ResponseSize int           `json:"response_size"`
	Anomalies    []Anomaly     `json:"anomalies,omitempty"`
	Payload      string        `json:"payload,omitempty"`
	Request      []byte        `json:"request,omitempty"`
	Response     []byte        `json:"response,omitempty"`
	CompletedAt  time.Time     `json:"completed_at"`
}

// Anomaly represents a detected anomaly
type Anomaly struct {
	Type        AnomalyType `json:"type"`
	Severity    string      `json:"severity"`
	Description string      `json:"description"`
	Evidence    string      `json:"evidence,omitempty"`
	Payload     string      `json:"payload,omitempty"`
}

// AnomalyType represents the type of anomaly
type AnomalyType string

const (
	AnomalyStatusCode  AnomalyType = "status_code"
	AnomalyTiming      AnomalyType = "timing"
	AnomalyError       AnomalyType = "error"
	AnomalyContentDiff AnomalyType = "content_diff"
	AnomalyReflection  AnomalyType = "reflection"
	AnomalyInjection   AnomalyType = "injection"
)

// TaskQueue manages task distribution
type TaskQueue struct {
	tasks    []*FuzzTask
	priority map[int][]*FuzzTask // Tasks by priority
}

// NewTaskQueue creates a new task queue
func NewTaskQueue() *TaskQueue {
	return &TaskQueue{
		tasks:    make([]*FuzzTask, 0),
		priority: make(map[int][]*FuzzTask),
	}
}

// Add adds a task to the queue
func (q *TaskQueue) Add(task *FuzzTask) {
	q.tasks = append(q.tasks, task)
	q.priority[task.Priority] = append(q.priority[task.Priority], task)
}

// Pop returns and removes the highest priority task
func (q *TaskQueue) Pop() *FuzzTask {
	if len(q.tasks) == 0 {
		return nil
	}

	// Find highest priority task
	var maxPriority int
	for p := range q.priority {
		if p > maxPriority && len(q.priority[p]) > 0 {
			maxPriority = p
		}
	}

	tasks := q.priority[maxPriority]
	if len(tasks) == 0 {
		return nil
	}

	task := tasks[0]
	q.priority[maxPriority] = tasks[1:]

	// Remove from main tasks list
	for i, t := range q.tasks {
		if t.ID == task.ID {
			q.tasks = append(q.tasks[:i], q.tasks[i+1:]...)
			break
		}
	}

	return task
}

// Len returns the number of tasks in the queue
func (q *TaskQueue) Len() int {
	return len(q.tasks)
}

// TaskGenerator generates fuzzing tasks from targets
type TaskGenerator struct {
	idCounter int64
}

// NewTaskGenerator creates a new task generator
func NewTaskGenerator() *TaskGenerator {
	return &TaskGenerator{}
}

// GenerateFromURL generates tasks for a single URL
func (g *TaskGenerator) GenerateFromURL(url, method string, payloads []string) []*FuzzTask {
	tasks := make([]*FuzzTask, 0, len(payloads))

	for _, payload := range payloads {
		g.idCounter++
		task := &FuzzTask{
			ID:         genTaskID(g.idCounter),
			Type:       TaskTypeFuzz,
			URL:        url,
			Method:     method,
			Payloads:   []string{payload},
			Priority:   5,
			MaxRetries: 3,
			Timeout:    30 * time.Second,
			CreatedAt:  time.Now(),
		}
		tasks = append(tasks, task)
	}

	return tasks
}

// GenerateCrawlTask generates a crawl task
func (g *TaskGenerator) GenerateCrawlTask(url string) *FuzzTask {
	g.idCounter++
	return &FuzzTask{
		ID:         genTaskID(g.idCounter),
		Type:       TaskTypeCrawl,
		URL:        url,
		Method:     "GET",
		Priority:   10, // High priority for crawling
		MaxRetries: 2,
		Timeout:    60 * time.Second,
		CreatedAt:  time.Now(),
	}
}

// GenerateVerifyTask generates a verification task
func (g *TaskGenerator) GenerateVerifyTask(original *FuzzTask, payload string) *FuzzTask {
	g.idCounter++
	return &FuzzTask{
		ID:         genTaskID(g.idCounter),
		Type:       TaskTypeVerify,
		URL:        original.URL,
		Method:     original.Method,
		Headers:    original.Headers,
		Body:       original.Body,
		Payloads:   []string{payload},
		Priority:   8, // High priority for verification
		MaxRetries: 1,
		Timeout:    30 * time.Second,
		CreatedAt:  time.Now(),
		Metadata: map[string]string{
			"original_task_id": original.ID,
		},
	}
}

// genTaskID generates a unique task ID
func genTaskID(counter int64) string {
	return fmt.Sprintf("task-%d-%d", time.Now().Unix(), counter)
}
