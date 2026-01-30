package ui

import (
	"testing"
	"time"
)

func TestNewDashboard(t *testing.T) {
	d := NewDashboard()

	if d == nil {
		t.Fatal("NewDashboard returned nil")
	}

	if d.status != StatusIdle {
		t.Errorf("Expected StatusIdle, got %v", d.status)
	}

	if d.stats == nil {
		t.Error("Stats should not be nil")
	}
}

func TestDashboard_StatusTransitions(t *testing.T) {
	d := NewDashboard()

	// Start
	d.Start()
	if d.status != StatusRunning {
		t.Errorf("Expected StatusRunning after Start, got %v", d.status)
	}

	// Pause
	d.Pause()
	if d.status != StatusPaused {
		t.Errorf("Expected StatusPaused after Pause, got %v", d.status)
	}

	// Resume
	d.Resume()
	if d.status != StatusRunning {
		t.Errorf("Expected StatusRunning after Resume, got %v", d.status)
	}

	// Stop
	d.Stop()
	if d.status != StatusStopped {
		t.Errorf("Expected StatusStopped after Stop, got %v", d.status)
	}
}

func TestDashboard_AddLog(t *testing.T) {
	d := NewDashboard()

	d.AddLog("INFO", "Test message 1")
	d.AddLog("ERROR", "Test message 2")

	if len(d.logs) != 2 {
		t.Errorf("Expected 2 logs, got %d", len(d.logs))
	}

	if d.logs[0].Level != "INFO" {
		t.Errorf("Expected first log level INFO, got %s", d.logs[0].Level)
	}

	if d.logs[1].Message != "Test message 2" {
		t.Errorf("Expected second log message 'Test message 2', got %s", d.logs[1].Message)
	}
}

func TestDashboard_LogTrimming(t *testing.T) {
	d := NewDashboard()
	d.maxLogs = 5

	// Add more logs than max
	for i := 0; i < 10; i++ {
		d.AddLog("INFO", "Message")
	}

	if len(d.logs) != 5 {
		t.Errorf("Expected %d logs after trimming, got %d", d.maxLogs, len(d.logs))
	}
}

func TestStats_RecordRequest(t *testing.T) {
	s := NewStats()

	s.RecordRequest(true, 100*time.Millisecond, false)
	s.RecordRequest(true, 200*time.Millisecond, false)
	s.RecordRequest(false, 50*time.Millisecond, true)

	if s.TotalRequests != 3 {
		t.Errorf("Expected 3 total requests, got %d", s.TotalRequests)
	}

	if s.SuccessCount != 2 {
		t.Errorf("Expected 2 success, got %d", s.SuccessCount)
	}

	if s.FailureCount != 1 {
		t.Errorf("Expected 1 failure, got %d", s.FailureCount)
	}

	if s.TimeoutCount != 1 {
		t.Errorf("Expected 1 timeout, got %d", s.TimeoutCount)
	}
}

func TestStats_RecordAnomaly(t *testing.T) {
	s := NewStats()

	s.RecordAnomaly("high")
	s.RecordAnomaly("critical")
	s.RecordAnomaly("medium")
	s.RecordAnomaly("low")
	s.RecordAnomaly("info")

	if s.AnomaliesFound != 5 {
		t.Errorf("Expected 5 anomalies, got %d", s.AnomaliesFound)
	}

	if s.HighSeverity != 2 {
		t.Errorf("Expected 2 high severity, got %d", s.HighSeverity)
	}

	if s.MediumSeverity != 1 {
		t.Errorf("Expected 1 medium severity, got %d", s.MediumSeverity)
	}

	if s.LowSeverity != 2 {
		t.Errorf("Expected 2 low severity, got %d", s.LowSeverity)
	}
}

func TestStats_UpdateProgress(t *testing.T) {
	s := NewStats()

	s.UpdateProgress(50, 100)

	if s.CurrentProgress != 0.5 {
		t.Errorf("Expected progress 0.5, got %f", s.CurrentProgress)
	}

	if s.CompletedTargets != 50 {
		t.Errorf("Expected 50 completed, got %d", s.CompletedTargets)
	}

	if s.TotalTargets != 100 {
		t.Errorf("Expected 100 total, got %d", s.TotalTargets)
	}
}

func TestStats_GetSuccessRate(t *testing.T) {
	s := NewStats()

	// No requests
	if s.GetSuccessRate() != 0 {
		t.Errorf("Expected 0 success rate with no requests, got %f", s.GetSuccessRate())
	}

	// Add requests
	s.RecordRequest(true, time.Millisecond, false)
	s.RecordRequest(true, time.Millisecond, false)
	s.RecordRequest(true, time.Millisecond, false)
	s.RecordRequest(false, time.Millisecond, false)

	rate := s.GetSuccessRate()
	if rate != 75.0 {
		t.Errorf("Expected 75%% success rate, got %f", rate)
	}
}

func TestStats_Snapshot(t *testing.T) {
	s := NewStats()

	s.RecordRequest(true, 100*time.Millisecond, false)
	s.UpdateProgress(10, 100)
	s.RecordAnomaly("high")

	snap := s.Snapshot()

	if snap.TotalRequests != 1 {
		t.Errorf("Snapshot TotalRequests: expected 1, got %d", snap.TotalRequests)
	}

	if snap.CurrentProgress != 0.1 {
		t.Errorf("Snapshot CurrentProgress: expected 0.1, got %f", snap.CurrentProgress)
	}

	if snap.AnomaliesFound != 1 {
		t.Errorf("Snapshot AnomaliesFound: expected 1, got %d", snap.AnomaliesFound)
	}
}

func TestProgressBar(t *testing.T) {
	p := NewProgressBar(50)

	p.SetProgress(0.5)
	p.SetETA("5m30s")

	rendered := p.Render()

	if rendered == "" {
		t.Error("ProgressBar Render returned empty string")
	}

	// Check that percentage is shown
	if len(rendered) < 10 {
		t.Error("ProgressBar Render output too short")
	}
}

func TestProgressBar_Bounds(t *testing.T) {
	p := NewProgressBar(50)

	// Test lower bound
	p.SetProgress(-0.5)
	if p.percentage != 0 {
		t.Errorf("Expected percentage clamped to 0, got %f", p.percentage)
	}

	// Test upper bound
	p.SetProgress(1.5)
	if p.percentage != 1 {
		t.Errorf("Expected percentage clamped to 1, got %f", p.percentage)
	}
}

func TestSpinnerProgress(t *testing.T) {
	s := NewSpinnerProgress()

	s.SetText("Loading data...")

	if !s.running {
		t.Error("Spinner should be running by default")
	}

	initialFrame := s.frame
	s.Tick()
	s.Tick()

	if s.frame == initialFrame {
		t.Error("Spinner frame should change after Tick")
	}

	s.Stop()
	if s.running {
		t.Error("Spinner should not be running after Stop")
	}
}

func TestStatus_String(t *testing.T) {
	tests := []struct {
		status   Status
		expected string
	}{
		{StatusIdle, "Idle"},
		{StatusRunning, "Running"},
		{StatusPaused, "Paused"},
		{StatusStopped, "Stopped"},
		{StatusCompleted, "Completed"},
	}

	for _, tt := range tests {
		if tt.status.String() != tt.expected {
			t.Errorf("Status.String(): expected %s, got %s", tt.expected, tt.status.String())
		}
	}
}

func TestFormatNumber(t *testing.T) {
	tests := []struct {
		input    int64
		expected string
	}{
		{0, "0"},
		{999, "999"},
		{1000, "1.0K"},
		{1500, "1.5K"},
		{1000000, "1.0M"},
		{1500000, "1.5M"},
	}

	for _, tt := range tests {
		result := formatNumber(tt.input)
		if result != tt.expected {
			t.Errorf("formatNumber(%d): expected %s, got %s", tt.input, tt.expected, result)
		}
	}
}

func TestFormatDuration(t *testing.T) {
	tests := []struct {
		input    time.Duration
		expected string
	}{
		{500 * time.Microsecond, "500µs"},
		{50 * time.Millisecond, "50ms"},
		{1500 * time.Millisecond, "1.5s"},
		{90 * time.Second, "1m30s"},
		{90 * time.Minute, "1h30m"},
	}

	for _, tt := range tests {
		result := formatDuration(tt.input)
		if result != tt.expected {
			t.Errorf("formatDuration(%v): expected %s, got %s", tt.input, tt.expected, result)
		}
	}
}

func BenchmarkStats_RecordRequest(b *testing.B) {
	s := NewStats()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		s.RecordRequest(true, 100*time.Millisecond, false)
	}
}

func BenchmarkStats_Snapshot(b *testing.B) {
	s := NewStats()

	// Add some data
	for i := 0; i < 1000; i++ {
		s.RecordRequest(true, 100*time.Millisecond, false)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		s.Snapshot()
	}
}

func BenchmarkDashboard_View(b *testing.B) {
	d := NewDashboard()
	d.width = 120
	d.height = 40
	d.Start()

	// Add some logs
	for i := 0; i < 20; i++ {
		d.AddLog("INFO", "Test message")
	}

	// Add some stats
	for i := 0; i < 100; i++ {
		d.stats.RecordRequest(true, 100*time.Millisecond, false)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		d.View()
	}
}
