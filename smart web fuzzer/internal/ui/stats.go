// Package ui provides statistics display components.
package ui

import (
	"fmt"
	"strings"
	"sync"
	"time"
)

// Stats holds fuzzing statistics
type Stats struct {
	mu sync.RWMutex

	// Request statistics
	TotalRequests int64
	SuccessCount  int64
	FailureCount  int64
	TimeoutCount  int64

	// Timing
	StartTime       time.Time
	LastRequestTime time.Time

	// Response times
	TotalResponseTime time.Duration
	MinResponseTime   time.Duration
	MaxResponseTime   time.Duration

	// Anomalies
	AnomaliesFound int64
	HighSeverity   int64
	MediumSeverity int64
	LowSeverity    int64

	// Progress
	CurrentProgress  float64
	TotalTargets     int64
	CompletedTargets int64

	// Rate
	rpsHistory     []float64
	lastRPSUpdate  time.Time
	requestsAtLast int64
}

// NewStats creates a new Stats instance
func NewStats() *Stats {
	return &Stats{
		StartTime:       time.Now(),
		MinResponseTime: time.Hour, // Start with max value
		rpsHistory:      make([]float64, 0, 60),
	}
}

// RecordRequest records a request result
func (s *Stats) RecordRequest(success bool, responseTime time.Duration, isTimeout bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.TotalRequests++
	s.LastRequestTime = time.Now()

	if success {
		s.SuccessCount++
	} else {
		s.FailureCount++
	}

	if isTimeout {
		s.TimeoutCount++
	}

	s.TotalResponseTime += responseTime

	if responseTime < s.MinResponseTime {
		s.MinResponseTime = responseTime
	}
	if responseTime > s.MaxResponseTime {
		s.MaxResponseTime = responseTime
	}
}

// RecordAnomaly records an anomaly finding
func (s *Stats) RecordAnomaly(severity string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.AnomaliesFound++

	switch strings.ToLower(severity) {
	case "high", "critical":
		s.HighSeverity++
	case "medium":
		s.MediumSeverity++
	case "low", "info":
		s.LowSeverity++
	}
}

// UpdateProgress updates the progress
func (s *Stats) UpdateProgress(completed, total int64) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.CompletedTargets = completed
	s.TotalTargets = total

	if total > 0 {
		s.CurrentProgress = float64(completed) / float64(total)
	}
}

// GetRPS returns the current requests per second
func (s *Stats) GetRPS() float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()

	elapsed := time.Since(s.StartTime).Seconds()
	if elapsed < 1 {
		return 0
	}
	return float64(s.TotalRequests) / elapsed
}

// GetAverageResponseTime returns the average response time
func (s *Stats) GetAverageResponseTime() time.Duration {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.TotalRequests == 0 {
		return 0
	}
	return s.TotalResponseTime / time.Duration(s.TotalRequests)
}

// GetElapsedTime returns the elapsed time since start
func (s *Stats) GetElapsedTime() time.Duration {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return time.Since(s.StartTime)
}

// GetSuccessRate returns the success rate percentage
func (s *Stats) GetSuccessRate() float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.TotalRequests == 0 {
		return 0
	}
	return float64(s.SuccessCount) / float64(s.TotalRequests) * 100
}

// GetETA returns estimated time remaining
func (s *Stats) GetETA() time.Duration {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.CompletedTargets == 0 || s.TotalTargets == 0 {
		return 0
	}

	elapsed := time.Since(s.StartTime)
	remaining := s.TotalTargets - s.CompletedTargets
	rate := float64(s.CompletedTargets) / elapsed.Seconds()

	if rate <= 0 {
		return 0
	}

	return time.Duration(float64(remaining)/rate) * time.Second
}

// Snapshot returns a copy of current stats
func (s *Stats) Snapshot() StatsSnapshot {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return StatsSnapshot{
		TotalRequests:    s.TotalRequests,
		SuccessCount:     s.SuccessCount,
		FailureCount:     s.FailureCount,
		TimeoutCount:     s.TimeoutCount,
		AnomaliesFound:   s.AnomaliesFound,
		HighSeverity:     s.HighSeverity,
		MediumSeverity:   s.MediumSeverity,
		LowSeverity:      s.LowSeverity,
		CurrentProgress:  s.CurrentProgress,
		TotalTargets:     s.TotalTargets,
		CompletedTargets: s.CompletedTargets,
		ElapsedTime:      time.Since(s.StartTime),
		AverageResponse:  s.GetAverageResponseTime(),
		RPS:              s.GetRPS(),
		SuccessRate:      s.GetSuccessRate(),
		ETA:              s.GetETA(),
	}
}

// StatsSnapshot is an immutable snapshot of stats
type StatsSnapshot struct {
	TotalRequests    int64
	SuccessCount     int64
	FailureCount     int64
	TimeoutCount     int64
	AnomaliesFound   int64
	HighSeverity     int64
	MediumSeverity   int64
	LowSeverity      int64
	CurrentProgress  float64
	TotalTargets     int64
	CompletedTargets int64
	ElapsedTime      time.Duration
	AverageResponse  time.Duration
	RPS              float64
	SuccessRate      float64
	ETA              time.Duration
}

// StatsView renders the statistics panel
type StatsView struct {
	width  int
	height int
}

// NewStatsView creates a new stats view
func NewStatsView(width, height int) *StatsView {
	return &StatsView{
		width:  width,
		height: height,
	}
}

// SetSize updates the view size
func (v *StatsView) SetSize(width, height int) {
	v.width = width
	v.height = height
}

// Render renders the stats view
func (v *StatsView) Render(snap StatsSnapshot) string {
	var b strings.Builder

	// Header
	b.WriteString(HeaderStyle.Render("📊 Statistics"))
	b.WriteString("\n\n")

	// Request stats
	b.WriteString(RenderLabelValue("Total Requests", formatNumber(snap.TotalRequests)))
	b.WriteString("\n")

	b.WriteString(RenderLabel("Success"))
	b.WriteString(" ")
	b.WriteString(SuccessStyle.Render(formatNumber(snap.SuccessCount)))
	b.WriteString(" | ")
	b.WriteString(RenderLabel("Failed"))
	b.WriteString(" ")
	b.WriteString(ErrorStyle.Render(formatNumber(snap.FailureCount)))
	b.WriteString("\n")

	b.WriteString(RenderLabelValue("Success Rate", fmt.Sprintf("%.1f%%", snap.SuccessRate)))
	b.WriteString("\n\n")

	// Performance
	b.WriteString(HeaderStyle.Render("⚡ Performance"))
	b.WriteString("\n\n")

	b.WriteString(RenderLabelValue("RPS", fmt.Sprintf("%.1f", snap.RPS)))
	b.WriteString("\n")
	b.WriteString(RenderLabelValue("Avg Response", formatDuration(snap.AverageResponse)))
	b.WriteString("\n")
	b.WriteString(RenderLabelValue("Elapsed", formatDuration(snap.ElapsedTime)))
	b.WriteString("\n\n")

	// Anomalies
	b.WriteString(HeaderStyle.Render("🔍 Anomalies"))
	b.WriteString("\n\n")

	b.WriteString(RenderLabelValue("Total Found", formatNumber(snap.AnomaliesFound)))
	b.WriteString("\n")

	if snap.AnomaliesFound > 0 {
		b.WriteString("  ")
		b.WriteString(AnomalyHighStyle.Render(fmt.Sprintf("High: %d", snap.HighSeverity)))
		b.WriteString(" | ")
		b.WriteString(AnomalyMediumStyle.Render(fmt.Sprintf("Med: %d", snap.MediumSeverity)))
		b.WriteString(" | ")
		b.WriteString(AnomalyLowStyle.Render(fmt.Sprintf("Low: %d", snap.LowSeverity)))
		b.WriteString("\n")
	}

	return StatsPanelStyle.Width(v.width).Render(b.String())
}

// Helper functions

func formatNumber(n int64) string {
	if n < 1000 {
		return fmt.Sprintf("%d", n)
	}
	if n < 1000000 {
		return fmt.Sprintf("%.1fK", float64(n)/1000)
	}
	return fmt.Sprintf("%.1fM", float64(n)/1000000)
}

func formatDuration(d time.Duration) string {
	if d < time.Millisecond {
		return fmt.Sprintf("%dµs", d.Microseconds())
	}
	if d < time.Second {
		return fmt.Sprintf("%dms", d.Milliseconds())
	}
	if d < time.Minute {
		return fmt.Sprintf("%.1fs", d.Seconds())
	}
	if d < time.Hour {
		return fmt.Sprintf("%dm%ds", int(d.Minutes()), int(d.Seconds())%60)
	}
	return fmt.Sprintf("%dh%dm", int(d.Hours()), int(d.Minutes())%60)
}
