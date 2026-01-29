// Package analyzer provides the unified analysis pipeline for response comparison.
// It integrates Baseline, SimHash, TLSH, and Filter components for comprehensive
// anomaly detection and response classification.
package analyzer

import (
	"sync"
	"time"
)

// AnalysisResult represents the comprehensive result of analyzing a response
type AnalysisResult struct {
	// Timing
	Timestamp    time.Time
	AnalysisTime time.Duration

	// Input data
	Input *AnalysisInput

	// Filter results
	Filtered     bool
	FilterResult *FilterResult

	// Baseline analysis
	BaselineAnomaly *AnomalyResult

	// Similarity analysis
	SimHashDistance   int
	SimHashSimilarity float64
	TLSHDistance      int
	TLSHSimilarity    float64

	// Composite scores
	AnomalyScore    float64 // 0-100, higher = more anomalous
	IsInteresting   bool    // Should this result be reported?
	InterestReasons []string

	// Classification
	Classification ResponseClassification
}

// ResponseClassification categorizes the response type
type ResponseClassification int

const (
	ClassificationNormal ResponseClassification = iota
	ClassificationAnomaly
	ClassificationInteresting
	ClassificationError
	ClassificationFiltered
)

func (c ResponseClassification) String() string {
	switch c {
	case ClassificationNormal:
		return "normal"
	case ClassificationAnomaly:
		return "anomaly"
	case ClassificationInteresting:
		return "interesting"
	case ClassificationError:
		return "error"
	case ClassificationFiltered:
		return "filtered"
	default:
		return "unknown"
	}
}

// AnalysisInput contains all data needed for analysis
type AnalysisInput struct {
	// Request info
	URL       string
	Payload   string
	Method    string
	RequestID int

	// Response data
	StatusCode    int
	Body          []byte
	Headers       map[string]string
	ResponseTime  time.Duration
	ContentLength int
	WordCount     int
}

// AnalyzerConfig holds configuration for the Analyzer
type AnalyzerConfig struct {
	// Baseline configuration
	BaselineConfig *BaselineConfig

	// TLSH configuration
	TLSHConfig *TLSHConfig

	// SimHash configuration
	SimHashNGramSize int

	// Anomaly detection thresholds
	AnomalyScoreThreshold     float64 // Score above this is anomalous
	InterestingScoreThreshold float64 // Score above this is interesting

	// Similarity thresholds
	SimilarityThreshold float64 // Similarity below this is notable

	// Weights for composite scoring
	TimeWeight       float64
	LengthWeight     float64
	SimHashWeight    float64
	TLSHWeight       float64
	StatusCodeWeight float64

	// Feature toggles
	EnableBaseline bool
	EnableSimHash  bool
	EnableTLSH     bool
}

// DefaultAnalyzerConfig returns sensible defaults
func DefaultAnalyzerConfig() *AnalyzerConfig {
	return &AnalyzerConfig{
		BaselineConfig: &BaselineConfig{
			MinSamples:                20,
			MaxSamples:                100,
			TimeThresholdMultiplier:   3.0,
			LengthThresholdMultiplier: 3.0,
			StdDevThreshold:           2.0,
		},
		TLSHConfig:                DefaultTLSHConfig(),
		SimHashNGramSize:          3,
		AnomalyScoreThreshold:     70.0,
		InterestingScoreThreshold: 40.0,
		SimilarityThreshold:       80.0,
		TimeWeight:                0.2,
		LengthWeight:              0.2,
		SimHashWeight:             0.3,
		TLSHWeight:                0.2,
		StatusCodeWeight:          0.1,
		EnableBaseline:            true,
		EnableSimHash:             true,
		EnableTLSH:                true,
	}
}

// Analyzer is the main analysis engine that integrates all components
type Analyzer struct {
	config *AnalyzerConfig
	mu     sync.RWMutex

	// Components
	baseline     *Baseline
	simhasher    *SimHasher
	tlshAnalyzer *TLSHAnalyzer
	filterChain  *FilterChain

	// Baseline references for comparison
	baselineSimHash SimHash
	baselineTLSH    *TLSHHash
	baselineBody    []byte

	// Statistics
	stats AnalyzerStats
}

// AnalyzerStats tracks analysis statistics
type AnalyzerStats struct {
	TotalAnalyzed    int
	TotalFiltered    int
	TotalAnomalies   int
	TotalInteresting int
	AverageScore     float64
}

// NewAnalyzer creates a new Analyzer with the given configuration
func NewAnalyzer(config *AnalyzerConfig) *Analyzer {
	if config == nil {
		config = DefaultAnalyzerConfig()
	}

	a := &Analyzer{
		config:      config,
		filterChain: NewFilterChain(FilterModeAny),
	}

	// Initialize components based on configuration
	if config.EnableBaseline {
		a.baseline = NewBaseline(config.BaselineConfig)
	}

	if config.EnableSimHash {
		a.simhasher = NewSimHasher(WithNGramSize(config.SimHashNGramSize))
	}

	if config.EnableTLSH {
		a.tlshAnalyzer = NewTLSHAnalyzer(config.TLSHConfig)
	}

	return a
}

// AddFilter adds a filter to the analyzer's filter chain
func (a *Analyzer) AddFilter(f Filter) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.filterChain.Add(f)
}

// SetFilters replaces the entire filter chain
func (a *Analyzer) SetFilters(chain *FilterChain) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.filterChain = chain
}

// LearnBaseline adds a sample to the baseline during the learning phase
func (a *Analyzer) LearnBaseline(input *AnalysisInput) bool {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.baseline == nil {
		return true
	}

	sample := Sample{
		ResponseTime:   input.ResponseTime,
		ResponseLength: input.ContentLength,
		WordCount:      input.WordCount,
		StatusCode:     input.StatusCode,
	}

	learned := a.baseline.AddSample(sample)

	// If just learned, compute baseline hashes
	if learned && a.baselineBody == nil && len(input.Body) > 0 {
		a.baselineBody = input.Body

		if a.simhasher != nil {
			a.baselineSimHash = a.simhasher.ComputeFromHTML(string(input.Body))
		}

		if a.tlshAnalyzer != nil {
			hash, err := a.tlshAnalyzer.ComputeHash(input.Body)
			if err == nil {
				a.baselineTLSH = hash
			}
		}
	}

	return learned
}

// IsLearned returns true if the baseline has been established
func (a *Analyzer) IsLearned() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()

	if a.baseline == nil {
		return true // No baseline = always "learned"
	}
	return a.baseline.IsLearned()
}

// LearningProgress returns the baseline learning progress (0-100)
func (a *Analyzer) LearningProgress() float64 {
	a.mu.RLock()
	defer a.mu.RUnlock()

	if a.baseline == nil {
		return 100.0
	}
	return a.baseline.Progress()
}

// Analyze performs comprehensive analysis on the input
func (a *Analyzer) Analyze(input *AnalysisInput) *AnalysisResult {
	startTime := time.Now()

	a.mu.Lock()
	defer a.mu.Unlock()

	result := &AnalysisResult{
		Timestamp:       startTime,
		Input:           input,
		InterestReasons: make([]string, 0),
		Classification:  ClassificationNormal,
	}

	// Step 1: Apply filters
	filterInput := &FilterInput{
		StatusCode:    input.StatusCode,
		Body:          input.Body,
		ContentLength: input.ContentLength,
		Headers:       input.Headers,
	}
	filterResult := a.filterChain.Apply(filterInput)
	result.FilterResult = filterResult

	if filterResult.Filtered {
		result.Filtered = true
		result.Classification = ClassificationFiltered
		a.stats.TotalFiltered++
		result.AnalysisTime = time.Since(startTime)
		return result
	}

	// Step 2: Baseline anomaly detection
	if a.baseline != nil && a.baseline.IsLearned() {
		sample := Sample{
			ResponseTime:   input.ResponseTime,
			ResponseLength: input.ContentLength,
			WordCount:      input.WordCount,
			StatusCode:     input.StatusCode,
		}
		anomaly := a.baseline.CheckAnomaly(sample)
		result.BaselineAnomaly = &anomaly

		if anomaly.IsAnomaly {
			result.InterestReasons = append(result.InterestReasons, anomaly.Reason)
		}
	}

	// Step 3: SimHash comparison
	if a.simhasher != nil && a.baselineSimHash != 0 {
		currentHash := a.simhasher.ComputeFromHTML(string(input.Body))
		result.SimHashDistance = a.baselineSimHash.Distance(currentHash)
		result.SimHashSimilarity = a.baselineSimHash.Similarity(currentHash)

		if result.SimHashSimilarity < a.config.SimilarityThreshold {
			result.InterestReasons = append(result.InterestReasons,
				"structural change detected (SimHash)")
		}
	}

	// Step 4: TLSH comparison
	if a.tlshAnalyzer != nil && a.baselineTLSH != nil && len(input.Body) >= 50 {
		currentHash, err := a.tlshAnalyzer.ComputeHash(input.Body)
		if err == nil {
			result.TLSHDistance = a.baselineTLSH.Distance(currentHash)
			result.TLSHSimilarity = a.baselineTLSH.Similarity(currentHash)

			if result.TLSHSimilarity < a.config.SimilarityThreshold {
				result.InterestReasons = append(result.InterestReasons,
					"content change detected (TLSH)")
			}
		}
	}

	// Step 5: Calculate composite anomaly score
	result.AnomalyScore = a.calculateAnomalyScore(result)

	// Step 6: Classify the result
	result.Classification = a.classify(result)
	result.IsInteresting = result.Classification == ClassificationAnomaly ||
		result.Classification == ClassificationInteresting

	// Update statistics
	a.stats.TotalAnalyzed++
	if result.Classification == ClassificationAnomaly {
		a.stats.TotalAnomalies++
	}
	if result.IsInteresting {
		a.stats.TotalInteresting++
	}
	a.stats.AverageScore = (a.stats.AverageScore*float64(a.stats.TotalAnalyzed-1) +
		result.AnomalyScore) / float64(a.stats.TotalAnalyzed)

	result.AnalysisTime = time.Since(startTime)
	return result
}

// calculateAnomalyScore computes a composite anomaly score
func (a *Analyzer) calculateAnomalyScore(result *AnalysisResult) float64 {
	score := 0.0
	weights := 0.0

	// Time-based score
	if result.BaselineAnomaly != nil && result.BaselineAnomaly.TimeSkew > 0 {
		timeScore := (result.BaselineAnomaly.TimeSkew - 1.0) * 50.0
		if timeScore > 100 {
			timeScore = 100
		}
		if timeScore < 0 {
			timeScore = 0
		}
		score += timeScore * a.config.TimeWeight
		weights += a.config.TimeWeight
	}

	// Length-based score
	if result.BaselineAnomaly != nil && result.BaselineAnomaly.LengthSkew > 0 {
		lengthScore := (result.BaselineAnomaly.LengthSkew - 1.0) * 50.0
		if lengthScore > 100 {
			lengthScore = 100
		}
		if lengthScore < 0 {
			lengthScore = 0
		}
		score += lengthScore * a.config.LengthWeight
		weights += a.config.LengthWeight
	}

	// SimHash score (inverse of similarity)
	if result.SimHashSimilarity > 0 || result.SimHashDistance > 0 {
		simhashScore := 100.0 - result.SimHashSimilarity
		score += simhashScore * a.config.SimHashWeight
		weights += a.config.SimHashWeight
	}

	// TLSH score (inverse of similarity)
	if result.TLSHSimilarity > 0 || result.TLSHDistance > 0 {
		tlshScore := 100.0 - result.TLSHSimilarity
		score += tlshScore * a.config.TLSHWeight
		weights += a.config.TLSHWeight
	}

	// Status code score
	if result.BaselineAnomaly != nil {
		for _, t := range result.BaselineAnomaly.Types {
			if t == AnomalyUnexpectedStatus {
				score += 100.0 * a.config.StatusCodeWeight
				weights += a.config.StatusCodeWeight
				break
			}
		}
	}

	if weights > 0 {
		return score / weights
	}
	return 0.0
}

// classify determines the classification based on the analysis result
func (a *Analyzer) classify(result *AnalysisResult) ResponseClassification {
	// Error status codes
	if result.Input.StatusCode >= 500 {
		return ClassificationError
	}

	// High anomaly score
	if result.AnomalyScore >= a.config.AnomalyScoreThreshold {
		return ClassificationAnomaly
	}

	// Medium score = interesting
	if result.AnomalyScore >= a.config.InterestingScoreThreshold {
		return ClassificationInteresting
	}

	// Baseline anomaly detected
	if result.BaselineAnomaly != nil && result.BaselineAnomaly.IsAnomaly {
		return ClassificationAnomaly
	}

	return ClassificationNormal
}

// Stats returns the current analysis statistics
func (a *Analyzer) Stats() AnalyzerStats {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.stats
}

// Reset clears all learned data and statistics
func (a *Analyzer) Reset() {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.baseline != nil {
		a.baseline.Reset()
	}

	a.baselineSimHash = 0
	a.baselineTLSH = nil
	a.baselineBody = nil

	a.stats = AnalyzerStats{}
}

// BaselineStats returns the current baseline statistics
func (a *Analyzer) BaselineStats() *BaselineStats {
	a.mu.RLock()
	defer a.mu.RUnlock()

	if a.baseline == nil {
		return nil
	}
	stats := a.baseline.Stats()
	return &stats
}

// --- Result Helper Methods ---

// IsAnomaly returns true if the result is classified as an anomaly
func (r *AnalysisResult) IsAnomaly() bool {
	return r.Classification == ClassificationAnomaly
}

// Summary returns a human-readable summary of the analysis
func (r *AnalysisResult) Summary() string {
	if r.Filtered {
		return "Filtered: " + r.FilterResult.Reason
	}

	summary := r.Classification.String()
	if len(r.InterestReasons) > 0 {
		summary += " - " + r.InterestReasons[0]
	}
	return summary
}
