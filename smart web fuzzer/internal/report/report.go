// Package report provides report generation for FluxFuzzer.
package report

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"
)

// Severity represents anomaly severity level
type Severity string

const (
	SeverityCritical Severity = "critical"
	SeverityHigh     Severity = "high"
	SeverityMedium   Severity = "medium"
	SeverityLow      Severity = "low"
	SeverityInfo     Severity = "info"
)

// AnomalyType represents the type of anomaly detected
type AnomalyType string

const (
	AnomalyStatusCode   AnomalyType = "status_code"
	AnomalyContentSize  AnomalyType = "content_size"
	AnomalyContentType  AnomalyType = "content_type"
	AnomalyResponseTime AnomalyType = "response_time"
	AnomalyError        AnomalyType = "error"
	AnomalySimilarity   AnomalyType = "similarity"
)

// Anomaly represents a detected anomaly
type Anomaly struct {
	ID          string      `json:"id"`
	Type        AnomalyType `json:"type"`
	Severity    Severity    `json:"severity"`
	URL         string      `json:"url"`
	Method      string      `json:"method"`
	Payload     string      `json:"payload,omitempty"`
	Description string      `json:"description"`
	StatusCode  int         `json:"status_code,omitempty"`
	Response    string      `json:"response,omitempty"`
	Timestamp   time.Time   `json:"timestamp"`
	Details     Details     `json:"details,omitempty"`
}

// Details contains additional anomaly details
type Details struct {
	Expected    string            `json:"expected,omitempty"`
	Actual      string            `json:"actual,omitempty"`
	Difference  float64           `json:"difference,omitempty"`
	Parameters  map[string]string `json:"parameters,omitempty"`
	RequestBody string            `json:"request_body,omitempty"`
	Headers     map[string]string `json:"headers,omitempty"`
}

// Statistics holds fuzzing statistics
type Statistics struct {
	TotalRequests   int64         `json:"total_requests"`
	SuccessCount    int64         `json:"success_count"`
	FailureCount    int64         `json:"failure_count"`
	TimeoutCount    int64         `json:"timeout_count"`
	AnomaliesFound  int64         `json:"anomalies_found"`
	Duration        time.Duration `json:"duration"`
	RequestsPerSec  float64       `json:"requests_per_sec"`
	AvgResponseTime time.Duration `json:"avg_response_time"`
	MinResponseTime time.Duration `json:"min_response_time"`
	MaxResponseTime time.Duration `json:"max_response_time"`
}

// MarshalJSON implements custom JSON marshaling for Statistics
func (s Statistics) MarshalJSON() ([]byte, error) {
	type Alias Statistics
	return json.Marshal(&struct {
		Alias
		Duration        string `json:"duration"`
		AvgResponseTime string `json:"avg_response_time"`
		MinResponseTime string `json:"min_response_time"`
		MaxResponseTime string `json:"max_response_time"`
	}{
		Alias:           Alias(s),
		Duration:        s.Duration.String(),
		AvgResponseTime: s.AvgResponseTime.String(),
		MinResponseTime: s.MinResponseTime.String(),
		MaxResponseTime: s.MaxResponseTime.String(),
	})
}

// Report represents a fuzzing report
type Report struct {
	// Metadata
	Title       string    `json:"title"`
	Description string    `json:"description,omitempty"`
	Version     string    `json:"version"`
	GeneratedAt time.Time `json:"generated_at"`

	// Target
	TargetURL string `json:"target_url"`

	// Statistics
	Statistics Statistics `json:"statistics"`

	// Anomalies
	Anomalies []Anomaly `json:"anomalies"`

	// Summary by severity
	SeverityCounts map[Severity]int `json:"severity_counts"`

	// Summary by type
	TypeCounts map[AnomalyType]int `json:"type_counts"`
}

// NewReport creates a new report
func NewReport(title, targetURL string) *Report {
	return &Report{
		Title:          title,
		Version:        "1.0",
		GeneratedAt:    time.Now(),
		TargetURL:      targetURL,
		Anomalies:      make([]Anomaly, 0),
		SeverityCounts: make(map[Severity]int),
		TypeCounts:     make(map[AnomalyType]int),
	}
}

// AddAnomaly adds an anomaly to the report
func (r *Report) AddAnomaly(a Anomaly) {
	r.Anomalies = append(r.Anomalies, a)
	r.SeverityCounts[a.Severity]++
	r.TypeCounts[a.Type]++
	r.Statistics.AnomaliesFound++
}

// SetStatistics sets the statistics
func (r *Report) SetStatistics(stats Statistics) {
	stats.AnomaliesFound = int64(len(r.Anomalies))
	r.Statistics = stats
}

// GetCriticalCount returns the count of critical anomalies
func (r *Report) GetCriticalCount() int {
	return r.SeverityCounts[SeverityCritical]
}

// GetHighCount returns the count of high severity anomalies
func (r *Report) GetHighCount() int {
	return r.SeverityCounts[SeverityHigh]
}

// GetMediumCount returns the count of medium severity anomalies
func (r *Report) GetMediumCount() int {
	return r.SeverityCounts[SeverityMedium]
}

// GetLowCount returns the count of low severity anomalies
func (r *Report) GetLowCount() int {
	return r.SeverityCounts[SeverityLow]
}

// FilterBySeverity returns anomalies with the given severity
func (r *Report) FilterBySeverity(severity Severity) []Anomaly {
	var filtered []Anomaly
	for _, a := range r.Anomalies {
		if a.Severity == severity {
			filtered = append(filtered, a)
		}
	}
	return filtered
}

// FilterByType returns anomalies with the given type
func (r *Report) FilterByType(anomalyType AnomalyType) []Anomaly {
	var filtered []Anomaly
	for _, a := range r.Anomalies {
		if a.Type == anomalyType {
			filtered = append(filtered, a)
		}
	}
	return filtered
}

// Generator is the interface for report generators
type Generator interface {
	Generate(report *Report, w io.Writer) error
	Extension() string
}

// Manager manages report generation
type Manager struct {
	generators map[string]Generator
	outputDir  string
}

// NewManager creates a new report manager
func NewManager(outputDir string) *Manager {
	m := &Manager{
		generators: make(map[string]Generator),
		outputDir:  outputDir,
	}

	// Register default generators
	m.RegisterGenerator("json", &JSONGenerator{Indent: true})
	m.RegisterGenerator("html", NewHTMLGenerator())
	m.RegisterGenerator("markdown", &MarkdownGenerator{})
	m.RegisterGenerator("md", &MarkdownGenerator{})

	return m
}

// RegisterGenerator registers a generator
func (m *Manager) RegisterGenerator(format string, gen Generator) {
	m.generators[format] = gen
}

// GetGenerator returns a generator by format
func (m *Manager) GetGenerator(format string) (Generator, bool) {
	gen, ok := m.generators[format]
	return gen, ok
}

// Generate generates a report in the specified format
func (m *Manager) Generate(report *Report, format string) (string, error) {
	gen, ok := m.generators[format]
	if !ok {
		return "", fmt.Errorf("unknown report format: %s", format)
	}

	// Create output directory if needed
	if err := os.MkdirAll(m.outputDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create output directory: %w", err)
	}

	// Generate filename
	timestamp := time.Now().Format("20060102_150405")
	filename := fmt.Sprintf("report_%s.%s", timestamp, gen.Extension())
	filepath := filepath.Join(m.outputDir, filename)

	// Create file
	f, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("failed to create report file: %w", err)
	}
	defer f.Close()

	// Generate report
	if err := gen.Generate(report, f); err != nil {
		return "", fmt.Errorf("failed to generate report: %w", err)
	}

	return filepath, nil
}

// GenerateAll generates reports in all registered formats
func (m *Manager) GenerateAll(report *Report) ([]string, error) {
	var paths []string
	seen := make(map[string]bool)

	for format, gen := range m.generators {
		// Skip duplicate extensions (e.g., md and markdown both use .md)
		ext := gen.Extension()
		if seen[ext] {
			continue
		}
		seen[ext] = true

		path, err := m.Generate(report, format)
		if err != nil {
			return paths, err
		}
		paths = append(paths, path)
	}

	return paths, nil
}

// WriteToWriter generates a report and writes to the given writer
func (m *Manager) WriteToWriter(report *Report, format string, w io.Writer) error {
	gen, ok := m.generators[format]
	if !ok {
		return fmt.Errorf("unknown report format: %s", format)
	}

	return gen.Generate(report, w)
}
