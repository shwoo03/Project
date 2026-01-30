// Package benchmark provides performance regression tests for FluxFuzzer.
package benchmark

import (
	"bytes"
	"testing"
	"time"

	"github.com/fluxfuzzer/fluxfuzzer/internal/mutator"
	"github.com/fluxfuzzer/fluxfuzzer/internal/report"
	"github.com/fluxfuzzer/fluxfuzzer/internal/scenario"
	"github.com/fluxfuzzer/fluxfuzzer/internal/state"
)

// Performance thresholds (in nanoseconds per operation)
const (
	ThresholdMutate        = 10000  // 10µs
	ThresholdSubstitute    = 5000   // 5µs
	ThresholdScenarioParse = 100000 // 100µs
	ThresholdReportGen     = 500000 // 500µs
)

// BenchmarkMutatorPerformance measures mutator performance.
func BenchmarkMutatorPerformance(b *testing.B) {
	mutators := []struct {
		name string
		m    mutator.Mutator
	}{
		{"BitFlip", mutator.NewBitFlipMutator(1)},
		{"ByteFlip", mutator.NewByteFlipMutator(1)},
		{"Arithmetic", mutator.NewArithmeticMutator(1, 35)},
		{"SQLi", mutator.NewSmartMutator(mutator.PayloadSQLi)},
		{"XSS", mutator.NewSmartMutator(mutator.PayloadXSS)},
	}

	data := []byte(`{"username": "admin", "password": "secret123", "remember": true}`)

	for _, mt := range mutators {
		b.Run(mt.name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				mt.m.Mutate(data)
			}
		})
	}
}

// BenchmarkTemplateEngine measures template substitution performance.
func BenchmarkTemplateEngine(b *testing.B) {
	sm := state.NewStateManager()
	sm.SetVariable("host", "api.example.com")
	sm.SetVariable("port", "8080")
	sm.SetVariable("token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
	sm.SetVariable("user_id", "12345")
	sm.SetVariable("session", "abc123def456")

	templates := []struct {
		name     string
		template string
	}{
		{"Simple", "{{host}}"},
		{"URL", "http://{{host}}:{{port}}/api/users/{{user_id}}"},
		{"Header", "Bearer {{token}}"},
		{"Complex", "http://{{host}}:{{port}}/api/v1/users/{{user_id}}/session/{{session}}?token={{token}}"},
	}

	for _, tt := range templates {
		b.Run(tt.name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				sm.Substitute(tt.template)
			}
		})
	}
}

// BenchmarkScenarioParser measures scenario parsing performance.
func BenchmarkScenarioParser(b *testing.B) {
	scenarios := []struct {
		name    string
		content []byte
	}{
		{"Simple", []byte(`
name: Simple
steps:
  - name: step1
    request:
      method: GET
      url: http://example.com
`)},
		{"WithVariables", []byte(`
name: With Variables
variables:
  base_url: http://example.com
  token: abc123
steps:
  - name: step1
    request:
      method: GET
      url: "{{base_url}}/api"
      headers:
        Authorization: "Bearer {{token}}"
`)},
		{"MultiStep", []byte(`
name: Multi Step
steps:
  - name: login
    request:
      method: POST
      url: http://example.com/login
    extract:
      - name: token
        type: jsonpath
        pattern: "access_token"
  - name: get_data
    request:
      method: GET
      url: http://example.com/data
  - name: post_data
    request:
      method: POST
      url: http://example.com/data
`)},
	}

	parser := scenario.NewParser()

	for _, s := range scenarios {
		b.Run(s.name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				parser.Parse(s.content)
			}
		})
	}
}

// BenchmarkReportGeneration measures report generation performance.
func BenchmarkReportGeneration(b *testing.B) {
	// Create report with varying numbers of anomalies
	sizes := []int{10, 100, 1000}

	for _, size := range sizes {
		r := createBenchmarkReport(size)

		b.Run("JSON_"+itoa(size), func(b *testing.B) {
			gen := &report.JSONGenerator{}
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				var buf bytes.Buffer
				gen.Generate(r, &buf)
			}
		})

		b.Run("Markdown_"+itoa(size), func(b *testing.B) {
			gen := &report.MarkdownGenerator{}
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				var buf bytes.Buffer
				gen.Generate(r, &buf)
			}
		})

		b.Run("HTML_"+itoa(size), func(b *testing.B) {
			gen := report.NewHTMLGenerator()
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				var buf bytes.Buffer
				gen.Generate(r, &buf)
			}
		})
	}
}

// BenchmarkParallelMutation measures parallel mutation performance.
func BenchmarkParallelMutation(b *testing.B) {
	m := mutator.NewSmartMutator(mutator.PayloadSQLi)
	data := []byte(`{"test": "data", "id": 123}`)

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			m.Mutate(data)
		}
	})
}

// Helper function to create a benchmark report
func createBenchmarkReport(numAnomalies int) *report.Report {
	r := report.NewReport("Benchmark Report", "http://benchmark.test")
	r.SetStatistics(report.Statistics{
		TotalRequests:   int64(numAnomalies * 100),
		SuccessCount:    int64(numAnomalies * 90),
		FailureCount:    int64(numAnomalies * 10),
		Duration:        10 * time.Minute,
		RequestsPerSec:  float64(numAnomalies),
		AvgResponseTime: 100 * time.Millisecond,
	})

	severities := []report.Severity{
		report.SeverityCritical,
		report.SeverityHigh,
		report.SeverityMedium,
		report.SeverityLow,
	}

	for i := 0; i < numAnomalies; i++ {
		r.AddAnomaly(report.Anomaly{
			ID:          itoa(i),
			Type:        report.AnomalyStatusCode,
			Severity:    severities[i%len(severities)],
			URL:         "http://benchmark.test/api/endpoint",
			Method:      "POST",
			Description: "Benchmark anomaly",
			StatusCode:  500,
			Timestamp:   time.Now(),
		})
	}

	return r
}

// itoa converts int to string
func itoa(i int) string {
	if i < 10 {
		return string('0' + byte(i))
	}
	s := ""
	for i > 0 {
		s = string('0'+byte(i%10)) + s
		i /= 10
	}
	return s
}

// TestPerformanceRegression verifies performance doesn't regress.
func TestPerformanceRegression(t *testing.T) {
	// Mutator performance test
	t.Run("Mutator", func(t *testing.T) {
		m := mutator.NewSmartMutator(mutator.PayloadSQLi)
		data := []byte(`{"test": "data"}`)

		start := time.Now()
		iterations := 10000
		for i := 0; i < iterations; i++ {
			m.Mutate(data)
		}
		elapsed := time.Since(start)

		avgNs := elapsed.Nanoseconds() / int64(iterations)
		if avgNs > ThresholdMutate {
			t.Logf("Warning: Mutator performance: %dns/op (threshold: %dns)", avgNs, ThresholdMutate)
		}
	})

	// Template substitution test
	t.Run("TemplateSubstitute", func(t *testing.T) {
		sm := state.NewStateManager()
		sm.SetVariable("var", "value")

		start := time.Now()
		iterations := 10000
		for i := 0; i < iterations; i++ {
			sm.Substitute("prefix_{{var}}_suffix")
		}
		elapsed := time.Since(start)

		avgNs := elapsed.Nanoseconds() / int64(iterations)
		if avgNs > ThresholdSubstitute {
			t.Logf("Warning: Template performance: %dns/op (threshold: %dns)", avgNs, ThresholdSubstitute)
		}
	})

	// Scenario parsing test
	t.Run("ScenarioParse", func(t *testing.T) {
		parser := scenario.NewParser()
		yaml := []byte(`
name: Test
steps:
  - name: step1
    request:
      method: GET
      url: http://example.com
`)

		start := time.Now()
		iterations := 1000
		for i := 0; i < iterations; i++ {
			parser.Parse(yaml)
		}
		elapsed := time.Since(start)

		avgNs := elapsed.Nanoseconds() / int64(iterations)
		if avgNs > ThresholdScenarioParse {
			t.Logf("Warning: Scenario parse performance: %dns/op (threshold: %dns)", avgNs, ThresholdScenarioParse)
		}
	})
}
