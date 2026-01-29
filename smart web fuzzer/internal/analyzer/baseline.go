// Package analyzer provides response analysis functionality for FluxFuzzer.
// It includes baseline learning, structural differential analysis, and anomaly detection.
package analyzer

import (
	"math"
	"sync"
	"time"
)

// BaselineStats holds statistical data for baseline comparison
type BaselineStats struct {
	// Response time statistics
	AvgResponseTime    time.Duration
	StdDevResponseTime time.Duration
	MinResponseTime    time.Duration
	MaxResponseTime    time.Duration

	// Response length statistics
	AvgResponseLength    float64
	StdDevResponseLength float64
	MinResponseLength    int
	MaxResponseLength    int

	// Sample count
	SampleCount int

	// Status code distribution
	StatusCodeCounts map[int]int

	// Word count statistics
	AvgWordCount    float64
	StdDevWordCount float64
}

// BaselineConfig holds configuration for baseline learning
type BaselineConfig struct {
	// MinSamples is the minimum number of samples required for a valid baseline
	MinSamples int

	// MaxSamples is the maximum number of samples to collect
	MaxSamples int

	// TimeThresholdMultiplier is the multiplier for time-based anomaly detection
	// e.g., 2.5 means responses > 2.5x average are flagged
	TimeThresholdMultiplier float64

	// LengthThresholdMultiplier is the multiplier for length-based anomaly detection
	LengthThresholdMultiplier float64

	// StdDevThreshold is the number of standard deviations for anomaly detection
	StdDevThreshold float64
}

// DefaultBaselineConfig returns sensible default configuration
func DefaultBaselineConfig() *BaselineConfig {
	return &BaselineConfig{
		MinSamples:                10,
		MaxSamples:                100,
		TimeThresholdMultiplier:   2.5,
		LengthThresholdMultiplier: 2.0,
		StdDevThreshold:           3.0,
	}
}

// Baseline manages baseline learning and anomaly detection
type Baseline struct {
	config *BaselineConfig
	stats  *BaselineStats
	mu     sync.RWMutex

	// Raw samples for calculation
	responseTimes   []time.Duration
	responseLengths []int
	wordCounts      []int
	statusCodes     []int

	// Learning state
	isLearned bool
}

// NewBaseline creates a new Baseline with the given configuration
func NewBaseline(config *BaselineConfig) *Baseline {
	if config == nil {
		config = DefaultBaselineConfig()
	}

	return &Baseline{
		config:          config,
		stats:           &BaselineStats{StatusCodeCounts: make(map[int]int)},
		responseTimes:   make([]time.Duration, 0, config.MaxSamples),
		responseLengths: make([]int, 0, config.MaxSamples),
		wordCounts:      make([]int, 0, config.MaxSamples),
		statusCodes:     make([]int, 0, config.MaxSamples),
	}
}

// Sample represents a single response sample for baseline learning
type Sample struct {
	ResponseTime   time.Duration
	ResponseLength int
	WordCount      int
	StatusCode     int
}

// AddSample adds a new sample to the baseline
// Returns true if the baseline has enough samples to be considered learned
func (b *Baseline) AddSample(sample Sample) bool {
	b.mu.Lock()
	defer b.mu.Unlock()

	// Don't add more samples if we've reached the max
	if len(b.responseTimes) >= b.config.MaxSamples {
		return b.isLearned
	}

	b.responseTimes = append(b.responseTimes, sample.ResponseTime)
	b.responseLengths = append(b.responseLengths, sample.ResponseLength)
	b.wordCounts = append(b.wordCounts, sample.WordCount)
	b.statusCodes = append(b.statusCodes, sample.StatusCode)

	// Update status code counts
	b.stats.StatusCodeCounts[sample.StatusCode]++
	b.stats.SampleCount = len(b.responseTimes)

	// Check if we have enough samples
	if len(b.responseTimes) >= b.config.MinSamples {
		b.calculateStats()
		b.isLearned = true
	}

	return b.isLearned
}

// calculateStats computes all statistical metrics from the raw samples
func (b *Baseline) calculateStats() {
	n := len(b.responseTimes)
	if n == 0 {
		return
	}

	// Calculate response time statistics
	var sumTime int64
	b.stats.MinResponseTime = b.responseTimes[0]
	b.stats.MaxResponseTime = b.responseTimes[0]

	for _, t := range b.responseTimes {
		sumTime += int64(t)
		if t < b.stats.MinResponseTime {
			b.stats.MinResponseTime = t
		}
		if t > b.stats.MaxResponseTime {
			b.stats.MaxResponseTime = t
		}
	}
	b.stats.AvgResponseTime = time.Duration(sumTime / int64(n))

	// Calculate response time standard deviation
	var sumSqDiffTime float64
	avgTimeNs := float64(b.stats.AvgResponseTime.Nanoseconds())
	for _, t := range b.responseTimes {
		diff := float64(t.Nanoseconds()) - avgTimeNs
		sumSqDiffTime += diff * diff
	}
	b.stats.StdDevResponseTime = time.Duration(math.Sqrt(sumSqDiffTime / float64(n)))

	// Calculate response length statistics
	var sumLength int
	b.stats.MinResponseLength = b.responseLengths[0]
	b.stats.MaxResponseLength = b.responseLengths[0]

	for _, l := range b.responseLengths {
		sumLength += l
		if l < b.stats.MinResponseLength {
			b.stats.MinResponseLength = l
		}
		if l > b.stats.MaxResponseLength {
			b.stats.MaxResponseLength = l
		}
	}
	b.stats.AvgResponseLength = float64(sumLength) / float64(n)

	// Calculate response length standard deviation
	var sumSqDiffLength float64
	for _, l := range b.responseLengths {
		diff := float64(l) - b.stats.AvgResponseLength
		sumSqDiffLength += diff * diff
	}
	b.stats.StdDevResponseLength = math.Sqrt(sumSqDiffLength / float64(n))

	// Calculate word count statistics
	var sumWords int
	for _, w := range b.wordCounts {
		sumWords += w
	}
	b.stats.AvgWordCount = float64(sumWords) / float64(n)

	var sumSqDiffWords float64
	for _, w := range b.wordCounts {
		diff := float64(w) - b.stats.AvgWordCount
		sumSqDiffWords += diff * diff
	}
	b.stats.StdDevWordCount = math.Sqrt(sumSqDiffWords / float64(n))
}

// IsLearned returns true if the baseline has collected enough samples
func (b *Baseline) IsLearned() bool {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return b.isLearned
}

// Stats returns a copy of the current baseline statistics
func (b *Baseline) Stats() BaselineStats {
	b.mu.RLock()
	defer b.mu.RUnlock()

	// Deep copy status code counts
	statusCodes := make(map[int]int)
	for k, v := range b.stats.StatusCodeCounts {
		statusCodes[k] = v
	}

	return BaselineStats{
		AvgResponseTime:      b.stats.AvgResponseTime,
		StdDevResponseTime:   b.stats.StdDevResponseTime,
		MinResponseTime:      b.stats.MinResponseTime,
		MaxResponseTime:      b.stats.MaxResponseTime,
		AvgResponseLength:    b.stats.AvgResponseLength,
		StdDevResponseLength: b.stats.StdDevResponseLength,
		MinResponseLength:    b.stats.MinResponseLength,
		MaxResponseLength:    b.stats.MaxResponseLength,
		SampleCount:          b.stats.SampleCount,
		StatusCodeCounts:     statusCodes,
		AvgWordCount:         b.stats.AvgWordCount,
		StdDevWordCount:      b.stats.StdDevWordCount,
	}
}

// AnomalyType represents the type of anomaly detected
type AnomalyType int

const (
	AnomalyNone AnomalyType = iota
	AnomalySlowResponse
	AnomalyFastResponse
	AnomalyLongResponse
	AnomalyShortResponse
	AnomalyUnexpectedStatus
	AnomalyMultiple
)

func (a AnomalyType) String() string {
	switch a {
	case AnomalyNone:
		return "none"
	case AnomalySlowResponse:
		return "slow_response"
	case AnomalyFastResponse:
		return "fast_response"
	case AnomalyLongResponse:
		return "long_response"
	case AnomalyShortResponse:
		return "short_response"
	case AnomalyUnexpectedStatus:
		return "unexpected_status"
	case AnomalyMultiple:
		return "multiple_anomalies"
	default:
		return "unknown"
	}
}

// AnomalyResult represents the result of anomaly detection
type AnomalyResult struct {
	IsAnomaly    bool
	Type         AnomalyType
	Types        []AnomalyType // All detected anomaly types
	TimeSkew     float64       // How much the response time differs from average (multiplier)
	LengthSkew   float64       // How much the response length differs from average (multiplier)
	TimeZScore   float64       // Z-score for response time
	LengthZScore float64       // Z-score for response length
	Reason       string
}

// CheckAnomaly checks if the given sample is anomalous compared to the baseline
func (b *Baseline) CheckAnomaly(sample Sample) AnomalyResult {
	b.mu.RLock()
	defer b.mu.RUnlock()

	result := AnomalyResult{
		Types: make([]AnomalyType, 0),
	}

	if !b.isLearned {
		return result
	}

	// Check response time anomaly
	if b.stats.AvgResponseTime > 0 {
		result.TimeSkew = float64(sample.ResponseTime) / float64(b.stats.AvgResponseTime)

		if b.stats.StdDevResponseTime > 0 {
			result.TimeZScore = float64(sample.ResponseTime-b.stats.AvgResponseTime) / float64(b.stats.StdDevResponseTime)
		}

		if result.TimeSkew > b.config.TimeThresholdMultiplier {
			result.Types = append(result.Types, AnomalySlowResponse)
		} else if result.TimeSkew < 1.0/b.config.TimeThresholdMultiplier {
			result.Types = append(result.Types, AnomalyFastResponse)
		}
	}

	// Check response length anomaly
	if b.stats.AvgResponseLength > 0 {
		result.LengthSkew = float64(sample.ResponseLength) / b.stats.AvgResponseLength

		if b.stats.StdDevResponseLength > 0 {
			result.LengthZScore = (float64(sample.ResponseLength) - b.stats.AvgResponseLength) / b.stats.StdDevResponseLength
		}

		if result.LengthSkew > b.config.LengthThresholdMultiplier {
			result.Types = append(result.Types, AnomalyLongResponse)
		} else if result.LengthSkew < 1.0/b.config.LengthThresholdMultiplier {
			result.Types = append(result.Types, AnomalyShortResponse)
		}
	}

	// Check for unexpected status code
	if _, exists := b.stats.StatusCodeCounts[sample.StatusCode]; !exists {
		result.Types = append(result.Types, AnomalyUnexpectedStatus)
	}

	// Determine final anomaly type
	if len(result.Types) > 0 {
		result.IsAnomaly = true
		if len(result.Types) == 1 {
			result.Type = result.Types[0]
		} else {
			result.Type = AnomalyMultiple
		}
		result.Reason = b.buildAnomalyReason(result)
	}

	return result
}

// buildAnomalyReason creates a human-readable reason for the anomaly
func (b *Baseline) buildAnomalyReason(result AnomalyResult) string {
	if len(result.Types) == 0 {
		return ""
	}

	reasons := make([]string, 0, len(result.Types))
	for _, t := range result.Types {
		switch t {
		case AnomalySlowResponse:
			reasons = append(reasons, "response time "+formatMultiplier(result.TimeSkew)+"x slower than baseline")
		case AnomalyFastResponse:
			reasons = append(reasons, "response time "+formatMultiplier(1/result.TimeSkew)+"x faster than baseline")
		case AnomalyLongResponse:
			reasons = append(reasons, "response length "+formatMultiplier(result.LengthSkew)+"x larger than baseline")
		case AnomalyShortResponse:
			reasons = append(reasons, "response length "+formatMultiplier(1/result.LengthSkew)+"x smaller than baseline")
		case AnomalyUnexpectedStatus:
			reasons = append(reasons, "unexpected status code")
		}
	}

	if len(reasons) == 1 {
		return reasons[0]
	}

	result2 := reasons[0]
	for i := 1; i < len(reasons); i++ {
		result2 += "; " + reasons[i]
	}
	return result2
}

func formatMultiplier(m float64) string {
	if m >= 10 {
		return "10+"
	}
	return string(rune('0'+int(m))) + "." + string(rune('0'+int(m*10)%10))
}

// Reset clears all baseline data and resets to learning mode
func (b *Baseline) Reset() {
	b.mu.Lock()
	defer b.mu.Unlock()

	b.responseTimes = make([]time.Duration, 0, b.config.MaxSamples)
	b.responseLengths = make([]int, 0, b.config.MaxSamples)
	b.wordCounts = make([]int, 0, b.config.MaxSamples)
	b.statusCodes = make([]int, 0, b.config.MaxSamples)
	b.stats = &BaselineStats{StatusCodeCounts: make(map[int]int)}
	b.isLearned = false
}

// Progress returns the learning progress as a percentage (0-100)
func (b *Baseline) Progress() float64 {
	b.mu.RLock()
	defer b.mu.RUnlock()

	if b.isLearned {
		return 100.0
	}

	return float64(len(b.responseTimes)) / float64(b.config.MinSamples) * 100.0
}
