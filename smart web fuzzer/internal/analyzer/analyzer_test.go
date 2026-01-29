package analyzer

import (
	"testing"
	"time"
)

func TestNewAnalyzer(t *testing.T) {
	// Test with nil config (should use defaults)
	a := NewAnalyzer(nil)
	if a == nil {
		t.Fatal("Expected non-nil analyzer")
	}

	if a.baseline == nil {
		t.Error("Expected baseline to be initialized")
	}

	if a.simhasher == nil {
		t.Error("Expected simhasher to be initialized")
	}

	if a.tlshAnalyzer == nil {
		t.Error("Expected tlshAnalyzer to be initialized")
	}
}

func TestAnalyzer_LearnBaseline(t *testing.T) {
	config := DefaultAnalyzerConfig()
	config.BaselineConfig.MinSamples = 5
	config.BaselineConfig.MaxSamples = 10
	a := NewAnalyzer(config)

	// Add samples until learned
	for i := 0; i < 5; i++ {
		input := &AnalysisInput{
			StatusCode:    200,
			Body:          []byte("<html><body><p>Test content for learning</p></body></html>"),
			ResponseTime:  100 * time.Millisecond,
			ContentLength: 50,
			WordCount:     10,
		}
		a.LearnBaseline(input)
	}

	if !a.IsLearned() {
		t.Error("Expected baseline to be learned after 5 samples")
	}

	progress := a.LearningProgress()
	if progress != 100.0 {
		t.Errorf("Expected 100%% progress, got %.2f%%", progress)
	}
}

func TestAnalyzer_Analyze_Filtered(t *testing.T) {
	a := NewAnalyzer(nil)
	a.AddFilter(NewStatusCodeFilter(404))

	input := &AnalysisInput{
		StatusCode:    404,
		Body:          []byte("Not Found"),
		ResponseTime:  50 * time.Millisecond,
		ContentLength: 9,
	}

	result := a.Analyze(input)

	if !result.Filtered {
		t.Error("Expected result to be filtered")
	}

	if result.Classification != ClassificationFiltered {
		t.Errorf("Expected classification 'filtered', got %s", result.Classification)
	}
}

func TestAnalyzer_Analyze_Normal(t *testing.T) {
	config := DefaultAnalyzerConfig()
	config.BaselineConfig.MinSamples = 3
	a := NewAnalyzer(config)

	// Learn baseline
	baseBody := []byte("<html><body><p>Standard response content here</p></body></html>")
	for i := 0; i < 3; i++ {
		input := &AnalysisInput{
			StatusCode:    200,
			Body:          baseBody,
			ResponseTime:  100 * time.Millisecond,
			ContentLength: len(baseBody),
			WordCount:     5,
		}
		a.LearnBaseline(input)
	}

	// Analyze similar response
	result := a.Analyze(&AnalysisInput{
		StatusCode:    200,
		Body:          baseBody,
		ResponseTime:  110 * time.Millisecond,
		ContentLength: len(baseBody),
		WordCount:     5,
	})

	if result.Filtered {
		t.Error("Expected result to NOT be filtered")
	}

	if result.Classification != ClassificationNormal {
		t.Errorf("Expected classification 'normal', got %s", result.Classification)
	}
}

func TestAnalyzer_Analyze_Anomaly(t *testing.T) {
	config := DefaultAnalyzerConfig()
	config.BaselineConfig.MinSamples = 3
	config.BaselineConfig.TimeThresholdMultiplier = 2.0
	a := NewAnalyzer(config)

	// Learn baseline with fast responses
	baseBody := []byte("<html><body><p>Standard response content here</p></body></html>")
	for i := 0; i < 3; i++ {
		input := &AnalysisInput{
			StatusCode:    200,
			Body:          baseBody,
			ResponseTime:  100 * time.Millisecond,
			ContentLength: len(baseBody),
			WordCount:     5,
		}
		a.LearnBaseline(input)
	}

	// Analyze with very slow response (10x slower)
	result := a.Analyze(&AnalysisInput{
		StatusCode:    200,
		Body:          baseBody,
		ResponseTime:  1000 * time.Millisecond, // 10x slower
		ContentLength: len(baseBody),
		WordCount:     5,
	})

	if result.BaselineAnomaly == nil {
		t.Fatal("Expected baseline anomaly to be detected")
	}

	if !result.BaselineAnomaly.IsAnomaly {
		t.Error("Expected anomaly to be detected for slow response")
	}
}

func TestAnalyzer_Analyze_StructuralChange(t *testing.T) {
	config := DefaultAnalyzerConfig()
	config.BaselineConfig.MinSamples = 3
	config.SimilarityThreshold = 90.0
	a := NewAnalyzer(config)

	// Learn baseline
	baseBody := []byte("<html><body><div><p>Normal page structure</p></div></body></html>")
	for i := 0; i < 3; i++ {
		input := &AnalysisInput{
			StatusCode:    200,
			Body:          baseBody,
			ResponseTime:  100 * time.Millisecond,
			ContentLength: len(baseBody),
			WordCount:     4,
		}
		a.LearnBaseline(input)
	}

	// Analyze with completely different structure
	differentBody := []byte("<html><body><table><tr><td>Error happened</td></tr></table></body></html>")
	result := a.Analyze(&AnalysisInput{
		StatusCode:    200,
		Body:          differentBody,
		ResponseTime:  100 * time.Millisecond,
		ContentLength: len(differentBody),
		WordCount:     2,
	})

	// Structure changed significantly
	if result.SimHashSimilarity == 100.0 {
		t.Error("Expected SimHash similarity to detect structural change")
	}
}

func TestAnalyzer_Stats(t *testing.T) {
	a := NewAnalyzer(nil)
	a.AddFilter(NewStatusCodeFilter(404))

	// Analyze some samples
	for i := 0; i < 5; i++ {
		a.Analyze(&AnalysisInput{StatusCode: 200, Body: []byte("OK")})
	}
	for i := 0; i < 3; i++ {
		a.Analyze(&AnalysisInput{StatusCode: 404, Body: []byte("Not Found")})
	}

	stats := a.Stats()

	if stats.TotalAnalyzed != 5 {
		t.Errorf("Expected 5 total analyzed (non-filtered), got %d", stats.TotalAnalyzed)
	}

	if stats.TotalFiltered != 3 {
		t.Errorf("Expected 3 filtered, got %d", stats.TotalFiltered)
	}
}

func TestAnalyzer_Reset(t *testing.T) {
	config := DefaultAnalyzerConfig()
	config.BaselineConfig.MinSamples = 3
	a := NewAnalyzer(config)

	// Learn baseline
	for i := 0; i < 3; i++ {
		a.LearnBaseline(&AnalysisInput{
			StatusCode:    200,
			Body:          []byte("Test"),
			ResponseTime:  100 * time.Millisecond,
			ContentLength: 4,
		})
	}

	if !a.IsLearned() {
		t.Error("Expected baseline to be learned")
	}

	a.Reset()

	if a.IsLearned() {
		t.Error("Expected baseline to be reset")
	}

	stats := a.Stats()
	if stats.TotalAnalyzed != 0 {
		t.Error("Expected stats to be reset")
	}
}

func TestAnalysisResult_Summary(t *testing.T) {
	// Filtered result
	filtered := &AnalysisResult{
		Filtered:       true,
		FilterResult:   FilteredBy("test", "test reason"),
		Classification: ClassificationFiltered,
	}

	if filtered.Summary() != "Filtered: test reason" {
		t.Errorf("Unexpected summary: %s", filtered.Summary())
	}

	// Normal result
	normal := &AnalysisResult{
		Classification:  ClassificationNormal,
		InterestReasons: []string{},
	}

	if normal.Summary() != "normal" {
		t.Errorf("Unexpected summary: %s", normal.Summary())
	}

	// Anomaly with reason
	anomaly := &AnalysisResult{
		Classification:  ClassificationAnomaly,
		InterestReasons: []string{"slow response detected"},
	}

	expected := "anomaly - slow response detected"
	if anomaly.Summary() != expected {
		t.Errorf("Expected '%s', got '%s'", expected, anomaly.Summary())
	}
}

func TestAnalyzer_DisabledComponents(t *testing.T) {
	config := DefaultAnalyzerConfig()
	config.EnableBaseline = false
	config.EnableSimHash = false
	config.EnableTLSH = false

	a := NewAnalyzer(config)

	if a.baseline != nil {
		t.Error("Expected baseline to be nil when disabled")
	}

	if a.simhasher != nil {
		t.Error("Expected simhasher to be nil when disabled")
	}

	if a.tlshAnalyzer != nil {
		t.Error("Expected tlshAnalyzer to be nil when disabled")
	}

	// Should still work without errors
	result := a.Analyze(&AnalysisInput{
		StatusCode: 200,
		Body:       []byte("Test"),
	})

	if result == nil {
		t.Error("Expected non-nil result even with disabled components")
	}
}

func BenchmarkAnalyzer_Analyze(b *testing.B) {
	config := DefaultAnalyzerConfig()
	config.BaselineConfig.MinSamples = 3
	a := NewAnalyzer(config)

	// Learn baseline
	baseBody := []byte("<html><body><p>Benchmark content here</p></body></html>")
	for i := 0; i < 3; i++ {
		a.LearnBaseline(&AnalysisInput{
			StatusCode:    200,
			Body:          baseBody,
			ResponseTime:  100 * time.Millisecond,
			ContentLength: len(baseBody),
			WordCount:     4,
		})
	}

	input := &AnalysisInput{
		StatusCode:    200,
		Body:          baseBody,
		ResponseTime:  100 * time.Millisecond,
		ContentLength: len(baseBody),
		WordCount:     4,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		a.Analyze(input)
	}
}
