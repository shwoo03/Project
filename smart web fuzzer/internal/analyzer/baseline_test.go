package analyzer

import (
	"testing"
	"time"
)

func TestBaseline_AddSample(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples: 5,
		MaxSamples: 10,
	})

	// Add samples
	for i := 0; i < 4; i++ {
		learned := b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			WordCount:      50,
			StatusCode:     200,
		})
		if learned {
			t.Errorf("Expected not learned after %d samples", i+1)
		}
	}

	// 5th sample should trigger learning
	learned := b.AddSample(Sample{
		ResponseTime:   100 * time.Millisecond,
		ResponseLength: 1000,
		WordCount:      50,
		StatusCode:     200,
	})
	if !learned {
		t.Error("Expected learned after 5 samples")
	}

	if !b.IsLearned() {
		t.Error("Expected IsLearned() to return true")
	}
}

func TestBaseline_Stats(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples: 3,
		MaxSamples: 10,
	})

	// Add varying samples
	samples := []Sample{
		{ResponseTime: 100 * time.Millisecond, ResponseLength: 1000, WordCount: 50, StatusCode: 200},
		{ResponseTime: 150 * time.Millisecond, ResponseLength: 1200, WordCount: 60, StatusCode: 200},
		{ResponseTime: 200 * time.Millisecond, ResponseLength: 800, WordCount: 40, StatusCode: 200},
	}

	for _, s := range samples {
		b.AddSample(s)
	}

	stats := b.Stats()

	// Check average response time (100+150+200)/3 = 150ms
	expectedAvgTime := 150 * time.Millisecond
	if stats.AvgResponseTime != expectedAvgTime {
		t.Errorf("Expected AvgResponseTime %v, got %v", expectedAvgTime, stats.AvgResponseTime)
	}

	// Check average response length (1000+1200+800)/3 = 1000
	if stats.AvgResponseLength != 1000 {
		t.Errorf("Expected AvgResponseLength 1000, got %v", stats.AvgResponseLength)
	}

	// Check min/max
	if stats.MinResponseTime != 100*time.Millisecond {
		t.Errorf("Expected MinResponseTime 100ms, got %v", stats.MinResponseTime)
	}
	if stats.MaxResponseTime != 200*time.Millisecond {
		t.Errorf("Expected MaxResponseTime 200ms, got %v", stats.MaxResponseTime)
	}

	// Check sample count
	if stats.SampleCount != 3 {
		t.Errorf("Expected SampleCount 3, got %d", stats.SampleCount)
	}

	// Check status code counts
	if stats.StatusCodeCounts[200] != 3 {
		t.Errorf("Expected StatusCodeCounts[200] = 3, got %d", stats.StatusCodeCounts[200])
	}
}

func TestBaseline_CheckAnomaly_SlowResponse(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples:                5,
		MaxSamples:                10,
		TimeThresholdMultiplier:   2.0,
		LengthThresholdMultiplier: 10.0, // Set high to avoid false positives
	})

	// Add baseline samples
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			WordCount:      50,
			StatusCode:     200,
		})
	}

	// Check normal response
	normalResult := b.CheckAnomaly(Sample{
		ResponseTime:   120 * time.Millisecond,
		ResponseLength: 1000,
		StatusCode:     200,
	})
	if normalResult.IsAnomaly {
		t.Error("Expected normal response to not be flagged as anomaly")
	}

	// Check slow response (3x slower)
	slowResult := b.CheckAnomaly(Sample{
		ResponseTime:   300 * time.Millisecond,
		ResponseLength: 1000,
		StatusCode:     200,
	})
	if !slowResult.IsAnomaly {
		t.Error("Expected slow response to be flagged as anomaly")
	}
	if slowResult.Type != AnomalySlowResponse {
		t.Errorf("Expected AnomalySlowResponse, got %v", slowResult.Type)
	}
}

func TestBaseline_CheckAnomaly_LongResponse(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples:                5,
		MaxSamples:                10,
		LengthThresholdMultiplier: 2.0,
	})

	// Add baseline samples
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			WordCount:      50,
			StatusCode:     200,
		})
	}

	// Check long response (3x longer)
	longResult := b.CheckAnomaly(Sample{
		ResponseTime:   100 * time.Millisecond,
		ResponseLength: 3000,
		StatusCode:     200,
	})
	if !longResult.IsAnomaly {
		t.Error("Expected long response to be flagged as anomaly")
	}
	if longResult.Type != AnomalyLongResponse {
		t.Errorf("Expected AnomalyLongResponse, got %v", longResult.Type)
	}
}

func TestBaseline_CheckAnomaly_UnexpectedStatus(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples: 5,
		MaxSamples: 10,
	})

	// Add baseline samples with 200 status
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			WordCount:      50,
			StatusCode:     200,
		})
	}

	// Check unexpected status code
	unexpectedResult := b.CheckAnomaly(Sample{
		ResponseTime:   100 * time.Millisecond,
		ResponseLength: 1000,
		StatusCode:     500,
	})
	if !unexpectedResult.IsAnomaly {
		t.Error("Expected unexpected status to be flagged as anomaly")
	}
	if unexpectedResult.Type != AnomalyUnexpectedStatus {
		t.Errorf("Expected AnomalyUnexpectedStatus, got %v", unexpectedResult.Type)
	}
}

func TestBaseline_CheckAnomaly_Multiple(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples:                5,
		MaxSamples:                10,
		TimeThresholdMultiplier:   2.0,
		LengthThresholdMultiplier: 2.0,
	})

	// Add baseline samples
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			WordCount:      50,
			StatusCode:     200,
		})
	}

	// Check multiple anomalies (slow + long + unexpected status)
	multiResult := b.CheckAnomaly(Sample{
		ResponseTime:   300 * time.Millisecond,
		ResponseLength: 3000,
		StatusCode:     500,
	})
	if !multiResult.IsAnomaly {
		t.Error("Expected multiple anomalies to be flagged")
	}
	if multiResult.Type != AnomalyMultiple {
		t.Errorf("Expected AnomalyMultiple, got %v", multiResult.Type)
	}
	if len(multiResult.Types) != 3 {
		t.Errorf("Expected 3 anomaly types, got %d", len(multiResult.Types))
	}
}

func TestBaseline_Reset(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples: 3,
		MaxSamples: 10,
	})

	// Learn baseline
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			StatusCode:     200,
		})
	}

	if !b.IsLearned() {
		t.Error("Expected baseline to be learned")
	}

	// Reset
	b.Reset()

	if b.IsLearned() {
		t.Error("Expected baseline to not be learned after reset")
	}

	stats := b.Stats()
	if stats.SampleCount != 0 {
		t.Errorf("Expected SampleCount 0 after reset, got %d", stats.SampleCount)
	}
}

func TestBaseline_Progress(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples: 10,
		MaxSamples: 100,
	})

	if b.Progress() != 0 {
		t.Errorf("Expected 0%% progress, got %.2f%%", b.Progress())
	}

	// Add 5 samples
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			StatusCode:     200,
		})
	}

	if b.Progress() != 50 {
		t.Errorf("Expected 50%% progress, got %.2f%%", b.Progress())
	}

	// Complete learning
	for i := 0; i < 5; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			StatusCode:     200,
		})
	}

	if b.Progress() != 100 {
		t.Errorf("Expected 100%% progress, got %.2f%%", b.Progress())
	}
}

func TestBaseline_MaxSamples(t *testing.T) {
	b := NewBaseline(&BaselineConfig{
		MinSamples: 3,
		MaxSamples: 5,
	})

	// Add more than max samples
	for i := 0; i < 10; i++ {
		b.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			StatusCode:     200,
		})
	}

	stats := b.Stats()
	if stats.SampleCount != 5 {
		t.Errorf("Expected max 5 samples, got %d", stats.SampleCount)
	}
}

func BenchmarkBaseline_AddSample(b *testing.B) {
	baseline := NewBaseline(DefaultBaselineConfig())

	sample := Sample{
		ResponseTime:   100 * time.Millisecond,
		ResponseLength: 1000,
		WordCount:      50,
		StatusCode:     200,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		baseline.Reset()
		for j := 0; j < 10; j++ {
			baseline.AddSample(sample)
		}
	}
}

func BenchmarkBaseline_CheckAnomaly(b *testing.B) {
	baseline := NewBaseline(DefaultBaselineConfig())

	// Learn baseline
	for i := 0; i < 10; i++ {
		baseline.AddSample(Sample{
			ResponseTime:   100 * time.Millisecond,
			ResponseLength: 1000,
			WordCount:      50,
			StatusCode:     200,
		})
	}

	sample := Sample{
		ResponseTime:   150 * time.Millisecond,
		ResponseLength: 1200,
		WordCount:      60,
		StatusCode:     200,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		baseline.CheckAnomaly(sample)
	}
}
