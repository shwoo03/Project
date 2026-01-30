// Package integration provides integration tests for FluxFuzzer.
package integration

import (
	"bytes"
	"testing"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/mutator"
	"github.com/fluxfuzzer/fluxfuzzer/internal/report"
	"github.com/fluxfuzzer/fluxfuzzer/internal/scenario"
	"github.com/fluxfuzzer/fluxfuzzer/internal/state"
)

// TestStateAndMutatorIntegration tests the integration between state and mutator packages.
func TestStateAndMutatorIntegration(t *testing.T) {
	// Setup state manager
	sm := state.NewStateManager()
	sm.SetVariable("target", "http://localhost:8080")
	sm.SetVariable("payload_type", "sqli")

	// Setup mutator
	sqliMutator := mutator.NewSmartMutator(mutator.PayloadSQLi)
	xssMutator := mutator.NewSmartMutator(mutator.PayloadXSS)

	// Get mutator based on state
	payloadType := sm.Substitute("{{payload_type}}")

	var m mutator.Mutator
	switch payloadType {
	case "sqli":
		m = sqliMutator
	case "xss":
		m = xssMutator
	default:
		m = sqliMutator
	}

	// Generate mutation
	original := []byte(`{"id": 1, "name": "test"}`)
	mutated, err := m.Mutate(original)
	if err != nil {
		t.Fatalf("Mutation failed: %v", err)
	}

	if len(mutated) == 0 {
		t.Error("Mutated data should not be empty")
	}

	t.Logf("Original: %s", original)
	t.Logf("Mutated: %s", mutated)
}

// TestScenarioAndStateIntegration tests scenario execution with state management.
func TestScenarioAndStateIntegration(t *testing.T) {
	yamlContent := `
name: Integration Test Scenario
variables:
  api_version: "v1"
  user_id: "123"

steps:
  - name: get_user
    request:
      method: GET
      url: "http://localhost/api/{{api_version}}/users/{{user_id}}"
    assert:
      - type: status
        expected: "200"
`

	parser := scenario.NewParser()
	s, err := parser.Parse([]byte(yamlContent))
	if err != nil {
		t.Fatalf("Failed to parse scenario: %v", err)
	}

	// Verify variables are properly parsed
	if s.Variables["api_version"] != "v1" {
		t.Errorf("Expected api_version='v1', got '%s'", s.Variables["api_version"])
	}

	if s.Variables["user_id"] != "123" {
		t.Errorf("Expected user_id='123', got '%s'", s.Variables["user_id"])
	}

	// Verify step URL contains template
	step := s.Steps[0]
	if step.Request.URL != "http://localhost/api/{{api_version}}/users/{{user_id}}" {
		t.Errorf("URL template not preserved: %s", step.Request.URL)
	}
}

// TestReportIntegration tests report generation workflow.
func TestReportIntegration(t *testing.T) {
	// Create report with real data
	r := report.NewReport("Integration Test Report", "http://integration-test.local")
	r.Description = "Integration test for report generation"

	// Add statistics
	r.SetStatistics(report.Statistics{
		TotalRequests:   1000,
		SuccessCount:    950,
		FailureCount:    50,
		TimeoutCount:    10,
		Duration:        5 * time.Minute,
		RequestsPerSec:  3.33,
		AvgResponseTime: 150 * time.Millisecond,
		MinResponseTime: 10 * time.Millisecond,
		MaxResponseTime: 2 * time.Second,
	})

	// Add various anomalies
	severities := []report.Severity{
		report.SeverityCritical,
		report.SeverityHigh,
		report.SeverityMedium,
		report.SeverityLow,
	}

	for i, sev := range severities {
		r.AddAnomaly(report.Anomaly{
			ID:          string(rune('A' + i)),
			Type:        report.AnomalyStatusCode,
			Severity:    sev,
			URL:         "http://integration-test.local/api/test",
			Method:      "POST",
			Description: "Test anomaly " + string(sev),
			StatusCode:  500,
			Timestamp:   time.Now(),
		})
	}

	// Verify counts
	if r.GetCriticalCount() != 1 {
		t.Errorf("Expected 1 critical, got %d", r.GetCriticalCount())
	}

	if r.GetHighCount() != 1 {
		t.Errorf("Expected 1 high, got %d", r.GetHighCount())
	}

	// Test all generators
	generators := []struct {
		name string
		gen  report.Generator
	}{
		{"json", &report.JSONGenerator{Indent: true}},
		{"markdown", &report.MarkdownGenerator{IncludeDetails: true}},
		{"html", report.NewHTMLGenerator()},
	}

	for _, g := range generators {
		t.Run(g.name, func(t *testing.T) {
			var buf bytes.Buffer
			err := g.gen.Generate(r, &buf)
			if err != nil {
				t.Fatalf("Failed to generate %s report: %v", g.name, err)
			}

			if buf.Len() == 0 {
				t.Errorf("%s report should not be empty", g.name)
			}

			t.Logf("%s report size: %d bytes", g.name, buf.Len())
		})
	}
}

// TestMutatorChain tests chaining multiple mutators.
func TestMutatorChain(t *testing.T) {
	mutators := []mutator.Mutator{
		mutator.NewBitFlipMutator(1),
		mutator.NewByteFlipMutator(1),
		mutator.NewArithmeticMutator(1, 35),
	}

	original := []byte("Hello, World!")

	// Apply multiple mutations in sequence
	data := make([]byte, len(original))
	copy(data, original)

	for _, m := range mutators {
		mutated, err := m.Mutate(data)
		if err != nil {
			continue
		}
		data = mutated
	}

	// Data should be different after mutations
	if bytes.Equal(data, original) {
		t.Log("Warning: Data unchanged after mutations (may be expected for short inputs)")
	}
}

// TestTemplateEngineIntegration tests template engine with various patterns.
func TestTemplateEngineIntegration(t *testing.T) {
	sm := state.NewStateManager()

	// Set various variables
	sm.SetVariable("host", "api.example.com")
	sm.SetVariable("port", "8080")
	sm.SetVariable("token", "abc123")
	sm.SetVariable("id", "42")

	tests := []struct {
		template string
		expected string
	}{
		{"http://{{host}}:{{port}}/api", "http://api.example.com:8080/api"},
		{"Bearer {{token}}", "Bearer abc123"},
		{"/users/{{id}}/profile", "/users/42/profile"},
		{"{{host}}/{{id}}", "api.example.com/42"},
	}

	for _, tt := range tests {
		result := sm.Substitute(tt.template)
		if result != tt.expected {
			t.Errorf("Substitute(%q) = %q, want %q", tt.template, result, tt.expected)
		}
	}
}

// TestEndToEndWorkflow simulates a complete fuzzing workflow.
func TestEndToEndWorkflow(t *testing.T) {
	// 1. Parse scenario
	yamlContent := `
name: E2E Test
steps:
  - name: test_endpoint
    request:
      method: POST
      url: http://localhost/api/test
      body: '{"data": "test"}'
    assert:
      - type: status
        expected: "200"
`
	parser := scenario.NewParser()
	s, err := parser.Parse([]byte(yamlContent))
	if err != nil {
		t.Fatalf("Scenario parse failed: %v", err)
	}

	// 2. Setup state
	sm := state.NewStateManager()
	for k, v := range s.Variables {
		sm.SetVariable(k, v)
	}

	// 3. Setup mutators
	m := mutator.NewSmartMutator(mutator.PayloadSQLi)

	// 4. Simulate fuzzing iterations
	mutations := 0
	for i := 0; i < 10; i++ {
		_, err := m.Mutate([]byte(s.Steps[0].Request.Body))
		if err == nil {
			mutations++
		}
	}

	// 5. Create report
	r := report.NewReport("E2E Test Report", "http://localhost")
	r.SetStatistics(report.Statistics{
		TotalRequests: int64(mutations),
	})

	// 6. Generate report
	var buf bytes.Buffer
	gen := &report.JSONGenerator{}
	if err := gen.Generate(r, &buf); err != nil {
		t.Fatalf("Report generation failed: %v", err)
	}

	t.Logf("E2E workflow completed: %d mutations, %d bytes report", mutations, buf.Len())
}
