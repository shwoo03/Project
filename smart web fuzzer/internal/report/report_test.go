package report

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestNewReport(t *testing.T) {
	r := NewReport("Test Report", "http://example.com")

	if r == nil {
		t.Fatal("NewReport returned nil")
	}

	if r.Title != "Test Report" {
		t.Errorf("Expected title 'Test Report', got '%s'", r.Title)
	}

	if r.TargetURL != "http://example.com" {
		t.Errorf("Expected target URL 'http://example.com', got '%s'", r.TargetURL)
	}

	if r.Version != "1.0" {
		t.Errorf("Expected version '1.0', got '%s'", r.Version)
	}
}

func TestReport_AddAnomaly(t *testing.T) {
	r := NewReport("Test", "http://example.com")

	a := Anomaly{
		ID:          "1",
		Type:        AnomalyStatusCode,
		Severity:    SeverityHigh,
		URL:         "http://example.com/test",
		Method:      "GET",
		Description: "Unexpected status code",
		StatusCode:  500,
		Timestamp:   time.Now(),
	}

	r.AddAnomaly(a)

	if len(r.Anomalies) != 1 {
		t.Errorf("Expected 1 anomaly, got %d", len(r.Anomalies))
	}

	if r.SeverityCounts[SeverityHigh] != 1 {
		t.Errorf("Expected 1 high severity count, got %d", r.SeverityCounts[SeverityHigh])
	}

	if r.TypeCounts[AnomalyStatusCode] != 1 {
		t.Errorf("Expected 1 status_code type count, got %d", r.TypeCounts[AnomalyStatusCode])
	}
}

func TestReport_FilterBySeverity(t *testing.T) {
	r := NewReport("Test", "http://example.com")

	r.AddAnomaly(Anomaly{Severity: SeverityHigh, Description: "High 1"})
	r.AddAnomaly(Anomaly{Severity: SeverityLow, Description: "Low 1"})
	r.AddAnomaly(Anomaly{Severity: SeverityHigh, Description: "High 2"})

	high := r.FilterBySeverity(SeverityHigh)
	if len(high) != 2 {
		t.Errorf("Expected 2 high severity anomalies, got %d", len(high))
	}

	low := r.FilterBySeverity(SeverityLow)
	if len(low) != 1 {
		t.Errorf("Expected 1 low severity anomaly, got %d", len(low))
	}
}

func TestReport_FilterByType(t *testing.T) {
	r := NewReport("Test", "http://example.com")

	r.AddAnomaly(Anomaly{Type: AnomalyStatusCode, Description: "Status 1"})
	r.AddAnomaly(Anomaly{Type: AnomalyResponseTime, Description: "Time 1"})
	r.AddAnomaly(Anomaly{Type: AnomalyStatusCode, Description: "Status 2"})

	statusAnomalies := r.FilterByType(AnomalyStatusCode)
	if len(statusAnomalies) != 2 {
		t.Errorf("Expected 2 status code anomalies, got %d", len(statusAnomalies))
	}
}

func TestJSONGenerator(t *testing.T) {
	r := NewReport("Test Report", "http://example.com")
	r.SetStatistics(Statistics{
		TotalRequests:  1000,
		SuccessCount:   950,
		FailureCount:   50,
		Duration:       time.Minute,
		RequestsPerSec: 16.67,
	})
	r.AddAnomaly(Anomaly{
		ID:          "1",
		Type:        AnomalyStatusCode,
		Severity:    SeverityHigh,
		Description: "Error 500",
	})

	gen := &JSONGenerator{Indent: true}

	var buf bytes.Buffer
	err := gen.Generate(r, &buf)
	if err != nil {
		t.Fatalf("Generate failed: %v", err)
	}

	output := buf.String()

	// Verify JSON is valid
	var parsed map[string]interface{}
	if err := json.Unmarshal([]byte(output), &parsed); err != nil {
		t.Fatalf("Invalid JSON output: %v", err)
	}

	if parsed["title"] != "Test Report" {
		t.Errorf("Expected title 'Test Report' in JSON")
	}
}

func TestJSONGenerator_Extension(t *testing.T) {
	gen := &JSONGenerator{}
	if gen.Extension() != "json" {
		t.Errorf("Expected extension 'json', got '%s'", gen.Extension())
	}
}

func TestMarkdownGenerator(t *testing.T) {
	r := NewReport("Test Report", "http://example.com")
	r.SetStatistics(Statistics{
		TotalRequests:   1000,
		SuccessCount:    950,
		FailureCount:    50,
		Duration:        time.Minute,
		RequestsPerSec:  16.67,
		AvgResponseTime: 100 * time.Millisecond,
	})
	r.AddAnomaly(Anomaly{
		ID:          "1",
		Type:        AnomalyStatusCode,
		Severity:    SeverityHigh,
		URL:         "http://example.com/api",
		Method:      "GET",
		Description: "Server error",
		StatusCode:  500,
		Timestamp:   time.Now(),
	})

	gen := &MarkdownGenerator{IncludeDetails: true}

	var buf bytes.Buffer
	err := gen.Generate(r, &buf)
	if err != nil {
		t.Fatalf("Generate failed: %v", err)
	}

	output := buf.String()

	// Check for key sections
	if !strings.Contains(output, "# Test Report") {
		t.Error("Expected title in Markdown output")
	}

	if !strings.Contains(output, "## 📊 Summary") {
		t.Error("Expected summary section in Markdown output")
	}

	if !strings.Contains(output, "## 🔍 Anomalies Found") {
		t.Error("Expected anomalies section in Markdown output")
	}

	if !strings.Contains(output, "🟠 High") {
		t.Error("Expected severity emoji in Markdown output")
	}
}

func TestMarkdownGenerator_NoAnomalies(t *testing.T) {
	r := NewReport("Clean Report", "http://example.com")

	gen := &MarkdownGenerator{}

	var buf bytes.Buffer
	err := gen.Generate(r, &buf)
	if err != nil {
		t.Fatalf("Generate failed: %v", err)
	}

	output := buf.String()

	if !strings.Contains(output, "No anomalies detected") {
		t.Error("Expected 'No anomalies detected' message")
	}
}

func TestHTMLGenerator(t *testing.T) {
	r := NewReport("Test Report", "http://example.com")
	r.SetStatistics(Statistics{
		TotalRequests:   1000,
		SuccessCount:    950,
		FailureCount:    50,
		Duration:        time.Minute,
		RequestsPerSec:  16.67,
		AvgResponseTime: 100 * time.Millisecond,
	})
	r.AddAnomaly(Anomaly{
		ID:          "1",
		Type:        AnomalyStatusCode,
		Severity:    SeverityHigh,
		URL:         "http://example.com/api",
		Method:      "GET",
		Description: "Server error",
		StatusCode:  500,
		Timestamp:   time.Now(),
	})

	gen := NewHTMLGenerator()

	var buf bytes.Buffer
	err := gen.Generate(r, &buf)
	if err != nil {
		t.Fatalf("Generate failed: %v", err)
	}

	output := buf.String()

	// Check for key HTML elements
	if !strings.Contains(output, "<!DOCTYPE html>") {
		t.Error("Expected DOCTYPE in HTML output")
	}

	if !strings.Contains(output, "<title>Test Report") {
		t.Error("Expected title in HTML output")
	}

	if !strings.Contains(output, "Statistics") {
		t.Error("Expected statistics section in HTML output")
	}

	if !strings.Contains(output, "Anomalies") {
		t.Error("Expected anomalies section in HTML output")
	}
}

func TestHTMLGenerator_Extension(t *testing.T) {
	gen := NewHTMLGenerator()
	if gen.Extension() != "html" {
		t.Errorf("Expected extension 'html', got '%s'", gen.Extension())
	}
}

func TestManager(t *testing.T) {
	// Create temp directory
	tmpDir := t.TempDir()

	m := NewManager(tmpDir)

	// Check default generators are registered
	if _, ok := m.GetGenerator("json"); !ok {
		t.Error("Expected json generator to be registered")
	}

	if _, ok := m.GetGenerator("html"); !ok {
		t.Error("Expected html generator to be registered")
	}

	if _, ok := m.GetGenerator("markdown"); !ok {
		t.Error("Expected markdown generator to be registered")
	}
}

func TestManager_Generate(t *testing.T) {
	tmpDir := t.TempDir()
	m := NewManager(tmpDir)

	r := NewReport("Test", "http://example.com")
	r.AddAnomaly(Anomaly{
		Severity:    SeverityMedium,
		Description: "Test anomaly",
	})

	// Generate JSON
	path, err := m.Generate(r, "json")
	if err != nil {
		t.Fatalf("Generate JSON failed: %v", err)
	}

	if !strings.HasSuffix(path, ".json") {
		t.Errorf("Expected .json extension, got %s", path)
	}

	// Verify file exists
	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Errorf("Report file was not created: %s", path)
	}
}

func TestManager_Generate_UnknownFormat(t *testing.T) {
	tmpDir := t.TempDir()
	m := NewManager(tmpDir)

	r := NewReport("Test", "http://example.com")

	_, err := m.Generate(r, "unknown")
	if err == nil {
		t.Error("Expected error for unknown format")
	}
}

func TestManager_GenerateAll(t *testing.T) {
	tmpDir := t.TempDir()
	m := NewManager(tmpDir)

	r := NewReport("Test", "http://example.com")

	paths, err := m.GenerateAll(r)
	if err != nil {
		t.Fatalf("GenerateAll failed: %v", err)
	}

	// Should generate json, html, and md
	if len(paths) < 3 {
		t.Errorf("Expected at least 3 files, got %d", len(paths))
	}

	// Verify all files exist
	for _, p := range paths {
		if _, err := os.Stat(p); os.IsNotExist(err) {
			t.Errorf("Report file was not created: %s", p)
		}
	}
}

func TestManager_WriteToWriter(t *testing.T) {
	m := NewManager("")

	r := NewReport("Test", "http://example.com")

	var buf bytes.Buffer
	err := m.WriteToWriter(r, "json", &buf)
	if err != nil {
		t.Fatalf("WriteToWriter failed: %v", err)
	}

	if buf.Len() == 0 {
		t.Error("Expected non-empty output")
	}
}

func TestTruncate(t *testing.T) {
	tests := []struct {
		input    string
		maxLen   int
		expected string
	}{
		{"short", 10, "short"},
		{"this is a long string", 10, "this is a ..."},
		{"exact", 5, "exact"},
	}

	for _, tt := range tests {
		result := truncate(tt.input, tt.maxLen)
		if result != tt.expected {
			t.Errorf("truncate(%q, %d) = %q, want %q", tt.input, tt.maxLen, result, tt.expected)
		}
	}
}

func TestSeverityEmoji(t *testing.T) {
	tests := []struct {
		severity Severity
		contains string
	}{
		{SeverityCritical, "Critical"},
		{SeverityHigh, "High"},
		{SeverityMedium, "Medium"},
		{SeverityLow, "Low"},
		{SeverityInfo, "Info"},
	}

	for _, tt := range tests {
		result := severityEmoji(tt.severity)
		if !strings.Contains(result, tt.contains) {
			t.Errorf("severityEmoji(%s) should contain %q, got %q", tt.severity, tt.contains, result)
		}
	}
}

func BenchmarkJSONGenerator(b *testing.B) {
	r := createTestReport(100)
	gen := &JSONGenerator{Indent: false}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		var buf bytes.Buffer
		gen.Generate(r, &buf)
	}
}

func BenchmarkMarkdownGenerator(b *testing.B) {
	r := createTestReport(100)
	gen := &MarkdownGenerator{}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		var buf bytes.Buffer
		gen.Generate(r, &buf)
	}
}

func BenchmarkHTMLGenerator(b *testing.B) {
	r := createTestReport(100)
	gen := NewHTMLGenerator()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		var buf bytes.Buffer
		gen.Generate(r, &buf)
	}
}

func createTestReport(numAnomalies int) *Report {
	r := NewReport("Benchmark Report", "http://example.com")
	r.SetStatistics(Statistics{
		TotalRequests:   10000,
		SuccessCount:    9500,
		FailureCount:    500,
		Duration:        10 * time.Minute,
		RequestsPerSec:  16.67,
		AvgResponseTime: 100 * time.Millisecond,
	})

	severities := []Severity{SeverityCritical, SeverityHigh, SeverityMedium, SeverityLow}
	types := []AnomalyType{AnomalyStatusCode, AnomalyResponseTime, AnomalyContentSize}

	for i := 0; i < numAnomalies; i++ {
		r.AddAnomaly(Anomaly{
			ID:          string(rune(i)),
			Type:        types[i%len(types)],
			Severity:    severities[i%len(severities)],
			URL:         "http://example.com/api/" + string(rune(i)),
			Method:      "GET",
			Description: "Test anomaly",
			StatusCode:  500,
			Timestamp:   time.Now(),
		})
	}

	return r
}

func TestIntegration_FullWorkflow(t *testing.T) {
	tmpDir := t.TempDir()

	// Create report
	r := NewReport("Integration Test", "http://example.com")
	r.Description = "Full workflow integration test"

	// Add statistics
	r.SetStatistics(Statistics{
		TotalRequests:   5000,
		SuccessCount:    4800,
		FailureCount:    200,
		TimeoutCount:    50,
		Duration:        5 * time.Minute,
		RequestsPerSec:  16.67,
		AvgResponseTime: 150 * time.Millisecond,
		MinResponseTime: 10 * time.Millisecond,
		MaxResponseTime: 2 * time.Second,
	})

	// Add various anomalies
	r.AddAnomaly(Anomaly{
		ID:          "1",
		Type:        AnomalyStatusCode,
		Severity:    SeverityCritical,
		URL:         "http://example.com/admin",
		Method:      "POST",
		Payload:     "' OR 1=1--",
		Description: "SQL Injection detected",
		StatusCode:  500,
		Timestamp:   time.Now(),
	})

	r.AddAnomaly(Anomaly{
		ID:          "2",
		Type:        AnomalyResponseTime,
		Severity:    SeverityMedium,
		URL:         "http://example.com/api/search",
		Method:      "GET",
		Description: "Slow response time",
		Timestamp:   time.Now(),
		Details: Details{
			Expected: "100ms",
			Actual:   "2s",
		},
	})

	// Create manager and generate all formats
	m := NewManager(tmpDir)
	paths, err := m.GenerateAll(r)
	if err != nil {
		t.Fatalf("GenerateAll failed: %v", err)
	}

	// Verify all files were created and have content
	for _, p := range paths {
		info, err := os.Stat(p)
		if os.IsNotExist(err) {
			t.Errorf("File not created: %s", p)
			continue
		}

		if info.Size() == 0 {
			t.Errorf("File is empty: %s", p)
		}

		// Verify extension
		ext := filepath.Ext(p)
		if ext != ".json" && ext != ".html" && ext != ".md" {
			t.Errorf("Unexpected file extension: %s", ext)
		}
	}
}
