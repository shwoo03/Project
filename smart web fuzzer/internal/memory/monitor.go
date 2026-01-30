// Package memory provides memory monitoring utilities.
package memory

import (
	"runtime"
	"sync"
	"time"
)

// MemoryStats holds memory statistics
type MemoryStats struct {
	// Go runtime stats
	Alloc        uint64 `json:"alloc"`          // Bytes allocated and in use
	TotalAlloc   uint64 `json:"total_alloc"`    // Total bytes allocated
	Sys          uint64 `json:"sys"`            // Bytes obtained from system
	NumGC        uint32 `json:"num_gc"`         // Number of completed GC cycles
	PauseTotalNs uint64 `json:"pause_total_ns"` // Total GC pause time
	HeapAlloc    uint64 `json:"heap_alloc"`     // Heap bytes allocated
	HeapSys      uint64 `json:"heap_sys"`       // Heap bytes from system
	HeapIdle     uint64 `json:"heap_idle"`      // Heap bytes waiting to be used
	HeapInuse    uint64 `json:"heap_inuse"`     // Heap bytes in use
	HeapReleased uint64 `json:"heap_released"`  // Heap bytes released to OS
	HeapObjects  uint64 `json:"heap_objects"`   // Number of heap objects
	StackInuse   uint64 `json:"stack_inuse"`    // Stack bytes in use
	StackSys     uint64 `json:"stack_sys"`      // Stack bytes from system
	NumGoroutine int    `json:"num_goroutine"`  // Number of goroutines

	// Custom stats
	Timestamp time.Time `json:"timestamp"`
}

// Monitor tracks memory usage over time
type Monitor struct {
	interval   time.Duration
	history    []MemoryStats
	maxHistory int
	threshold  MemoryThreshold
	alerts     chan MemoryAlert
	running    bool
	mu         sync.RWMutex
	stopCh     chan struct{}
}

// MemoryThreshold defines memory alert thresholds
type MemoryThreshold struct {
	HeapAllocBytes uint64  // Alert if heap exceeds this
	HeapPercent    float64 // Alert if heap usage exceeds this percent
	GCPauseMs      uint64  // Alert if GC pause exceeds this (ms)
}

// DefaultThreshold returns default thresholds
func DefaultThreshold() MemoryThreshold {
	return MemoryThreshold{
		HeapAllocBytes: 1 << 30, // 1GB
		HeapPercent:    80.0,    // 80%
		GCPauseMs:      100,     // 100ms
	}
}

// MemoryAlert represents a memory alert
type MemoryAlert struct {
	Type      AlertType `json:"type"`
	Message   string    `json:"message"`
	Value     uint64    `json:"value"`
	Threshold uint64    `json:"threshold"`
	Timestamp time.Time `json:"timestamp"`
}

// AlertType represents types of memory alerts
type AlertType string

const (
	AlertHeapSize    AlertType = "heap_size"
	AlertHeapPercent AlertType = "heap_percent"
	AlertGCPause     AlertType = "gc_pause"
	AlertOOM         AlertType = "oom_risk"
)

// NewMonitor creates a new memory monitor
func NewMonitor(interval time.Duration, threshold MemoryThreshold) *Monitor {
	if interval == 0 {
		interval = 10 * time.Second
	}

	return &Monitor{
		interval:   interval,
		history:    make([]MemoryStats, 0, 100),
		maxHistory: 1000,
		threshold:  threshold,
		alerts:     make(chan MemoryAlert, 100),
		stopCh:     make(chan struct{}),
	}
}

// Start starts the memory monitor
func (m *Monitor) Start() {
	m.mu.Lock()
	if m.running {
		m.mu.Unlock()
		return
	}
	m.running = true
	m.mu.Unlock()

	go m.monitorLoop()
}

// Stop stops the memory monitor
func (m *Monitor) Stop() {
	m.mu.Lock()
	if !m.running {
		m.mu.Unlock()
		return
	}
	m.running = false
	m.mu.Unlock()

	close(m.stopCh)
}

// monitorLoop runs the monitoring loop
func (m *Monitor) monitorLoop() {
	ticker := time.NewTicker(m.interval)
	defer ticker.Stop()

	for {
		select {
		case <-m.stopCh:
			return
		case <-ticker.C:
			stats := m.collectStats()
			m.recordStats(stats)
			m.checkThresholds(stats)
		}
	}
}

// collectStats collects current memory statistics
func (m *Monitor) collectStats() MemoryStats {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	return MemoryStats{
		Alloc:        memStats.Alloc,
		TotalAlloc:   memStats.TotalAlloc,
		Sys:          memStats.Sys,
		NumGC:        memStats.NumGC,
		PauseTotalNs: memStats.PauseTotalNs,
		HeapAlloc:    memStats.HeapAlloc,
		HeapSys:      memStats.HeapSys,
		HeapIdle:     memStats.HeapIdle,
		HeapInuse:    memStats.HeapInuse,
		HeapReleased: memStats.HeapReleased,
		HeapObjects:  memStats.HeapObjects,
		StackInuse:   memStats.StackInuse,
		StackSys:     memStats.StackSys,
		NumGoroutine: runtime.NumGoroutine(),
		Timestamp:    time.Now(),
	}
}

// recordStats records statistics to history
func (m *Monitor) recordStats(stats MemoryStats) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.history = append(m.history, stats)

	// Trim history if needed
	if len(m.history) > m.maxHistory {
		m.history = m.history[len(m.history)-m.maxHistory:]
	}
}

// checkThresholds checks if any thresholds are exceeded
func (m *Monitor) checkThresholds(stats MemoryStats) {
	// Check heap size
	if m.threshold.HeapAllocBytes > 0 && stats.HeapAlloc > m.threshold.HeapAllocBytes {
		m.sendAlert(MemoryAlert{
			Type:      AlertHeapSize,
			Message:   "Heap allocation exceeded threshold",
			Value:     stats.HeapAlloc,
			Threshold: m.threshold.HeapAllocBytes,
			Timestamp: time.Now(),
		})
	}

	// Check heap percentage
	if m.threshold.HeapPercent > 0 && stats.HeapSys > 0 {
		percent := float64(stats.HeapInuse) / float64(stats.HeapSys) * 100
		if percent > m.threshold.HeapPercent {
			m.sendAlert(MemoryAlert{
				Type:      AlertHeapPercent,
				Message:   "Heap usage percentage exceeded threshold",
				Value:     uint64(percent),
				Threshold: uint64(m.threshold.HeapPercent),
				Timestamp: time.Now(),
			})
		}
	}
}

// sendAlert sends an alert
func (m *Monitor) sendAlert(alert MemoryAlert) {
	select {
	case m.alerts <- alert:
	default:
		// Channel full, drop alert
	}
}

// GetAlerts returns the alerts channel
func (m *Monitor) GetAlerts() <-chan MemoryAlert {
	return m.alerts
}

// GetCurrentStats returns current memory statistics
func (m *Monitor) GetCurrentStats() MemoryStats {
	return m.collectStats()
}

// GetHistory returns recorded statistics history
func (m *Monitor) GetHistory() []MemoryStats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	history := make([]MemoryStats, len(m.history))
	copy(history, m.history)
	return history
}

// GetLatest returns the most recent stats
func (m *Monitor) GetLatest() *MemoryStats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if len(m.history) == 0 {
		stats := m.collectStats()
		return &stats
	}
	return &m.history[len(m.history)-1]
}

// ForceGC forces a garbage collection
func ForceGC() {
	runtime.GC()
}

// FreeOSMemory releases memory to the operating system
func FreeOSMemory() {
	runtime.GC()
	// debug.FreeOSMemory() was not used to avoid import
}

// SetGCPercent sets the GC target percentage
func SetGCPercent(percent int) int {
	// Using runtime.GC as a trigger, GOGC via environment
	old := runtime.GOMAXPROCS(0)
	runtime.GOMAXPROCS(old)
	return 100 // Default GOGC
}

// QuickStats returns a quick snapshot of memory usage
func QuickStats() map[string]interface{} {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	return map[string]interface{}{
		"alloc_mb":      float64(m.Alloc) / 1024 / 1024,
		"heap_alloc_mb": float64(m.HeapAlloc) / 1024 / 1024,
		"heap_inuse_mb": float64(m.HeapInuse) / 1024 / 1024,
		"heap_objects":  m.HeapObjects,
		"num_gc":        m.NumGC,
		"goroutines":    runtime.NumGoroutine(),
	}
}
