// Package analyzer provides TLSH (Trend Micro Locality Sensitive Hash) integration.
// TLSH is designed for detecting similar files and content with fuzzy matching.
package analyzer

import (
	"errors"

	"github.com/glaslos/tlsh"
)

// TLSHHash represents a TLSH hash value
type TLSHHash struct {
	hash *tlsh.TLSH
	raw  string
}

// TLSHConfig holds configuration for TLSH analysis
type TLSHConfig struct {
	// MinDataSize is the minimum content size required for TLSH computation
	// TLSH requires at least 50 bytes for meaningful hash
	MinDataSize int

	// SimilarityThreshold is the maximum distance for content to be considered similar
	// Lower values = more similar required (typical: 30-100)
	SimilarityThreshold int

	// HighSimilarityThreshold for very similar content (typical: 10-30)
	HighSimilarityThreshold int
}

// DefaultTLSHConfig returns sensible default configuration
func DefaultTLSHConfig() *TLSHConfig {
	return &TLSHConfig{
		MinDataSize:             50,
		SimilarityThreshold:     100,
		HighSimilarityThreshold: 30,
	}
}

// TLSHAnalyzer provides TLSH-based similarity analysis
type TLSHAnalyzer struct {
	config   *TLSHConfig
	baseline *TLSHHash
}

// NewTLSHAnalyzer creates a new TLSH analyzer
func NewTLSHAnalyzer(config *TLSHConfig) *TLSHAnalyzer {
	if config == nil {
		config = DefaultTLSHConfig()
	}
	return &TLSHAnalyzer{
		config: config,
	}
}

// ComputeHash computes the TLSH hash for the given content
func (a *TLSHAnalyzer) ComputeHash(content []byte) (*TLSHHash, error) {
	if len(content) < a.config.MinDataSize {
		return nil, errors.New("content too small for TLSH computation")
	}

	hash, err := tlsh.HashBytes(content)
	if err != nil {
		return nil, err
	}

	return &TLSHHash{
		hash: hash,
		raw:  hash.String(),
	}, nil
}

// ComputeHashString computes TLSH hash from a string
func (a *TLSHAnalyzer) ComputeHashString(content string) (*TLSHHash, error) {
	return a.ComputeHash([]byte(content))
}

// SetBaseline sets the baseline hash for comparison
func (a *TLSHAnalyzer) SetBaseline(hash *TLSHHash) {
	a.baseline = hash
}

// SetBaselineFromContent computes and sets baseline from content
func (a *TLSHAnalyzer) SetBaselineFromContent(content []byte) error {
	hash, err := a.ComputeHash(content)
	if err != nil {
		return err
	}
	a.baseline = hash
	return nil
}

// HasBaseline returns true if a baseline has been set
func (a *TLSHAnalyzer) HasBaseline() bool {
	return a.baseline != nil
}

// TLSHResult represents the result of TLSH comparison
type TLSHResult struct {
	// Distance is the TLSH distance (0 = identical, higher = more different)
	Distance int

	// Similarity is the similarity percentage (100 = identical, 0 = completely different)
	Similarity float64

	// IsSimilar indicates if content is within similarity threshold
	IsSimilar bool

	// IsHighlySimilar indicates if content is within high similarity threshold
	IsHighlySimilar bool

	// BaselineHash is the baseline hash string
	BaselineHash string

	// CurrentHash is the current content hash string
	CurrentHash string
}

// Compare compares the given content against the baseline
func (a *TLSHAnalyzer) Compare(content []byte) (*TLSHResult, error) {
	if a.baseline == nil {
		return nil, errors.New("baseline not set")
	}

	currentHash, err := a.ComputeHash(content)
	if err != nil {
		return nil, err
	}

	return a.CompareHashes(a.baseline, currentHash), nil
}

// CompareString compares string content against baseline
func (a *TLSHAnalyzer) CompareString(content string) (*TLSHResult, error) {
	return a.Compare([]byte(content))
}

// CompareHashes compares two TLSH hashes directly
func (a *TLSHAnalyzer) CompareHashes(hash1, hash2 *TLSHHash) *TLSHResult {
	distance := hash1.hash.Diff(hash2.hash)

	// Calculate similarity percentage
	// TLSH distance typically ranges from 0 to ~300+
	// We normalize to a percentage (inverse relationship)
	maxDistance := 300.0
	similarity := (1.0 - float64(distance)/maxDistance) * 100.0
	if similarity < 0 {
		similarity = 0
	}

	return &TLSHResult{
		Distance:        distance,
		Similarity:      similarity,
		IsSimilar:       distance <= a.config.SimilarityThreshold,
		IsHighlySimilar: distance <= a.config.HighSimilarityThreshold,
		BaselineHash:    hash1.raw,
		CurrentHash:     hash2.raw,
	}
}

// CompareContents compares two content byte slices directly
func (a *TLSHAnalyzer) CompareContents(content1, content2 []byte) (*TLSHResult, error) {
	hash1, err := a.ComputeHash(content1)
	if err != nil {
		return nil, err
	}

	hash2, err := a.ComputeHash(content2)
	if err != nil {
		return nil, err
	}

	return a.CompareHashes(hash1, hash2), nil
}

// String returns the hash string representation
func (h *TLSHHash) String() string {
	if h == nil || h.hash == nil {
		return ""
	}
	return h.raw
}

// Distance calculates distance between two TLSHHash values
func (h *TLSHHash) Distance(other *TLSHHash) int {
	if h == nil || other == nil || h.hash == nil || other.hash == nil {
		return -1
	}
	return h.hash.Diff(other.hash)
}

// Similarity returns similarity percentage between two hashes
func (h *TLSHHash) Similarity(other *TLSHHash) float64 {
	distance := h.Distance(other)
	if distance < 0 {
		return 0
	}
	maxDistance := 300.0
	similarity := (1.0 - float64(distance)/maxDistance) * 100.0
	if similarity < 0 {
		return 0
	}
	return similarity
}

// TLSHSimilarityLevel represents categorized similarity levels
type TLSHSimilarityLevel int

const (
	TLSHIdentical       TLSHSimilarityLevel = iota // Distance 0
	TLSHNearlySame                                 // Distance 1-10
	TLSHVerySimilar                                // Distance 11-30
	TLSHSimilar                                    // Distance 31-100
	TLSHSomewhatSimilar                            // Distance 101-200
	TLSHDifferent                                  // Distance 201+
)

func (l TLSHSimilarityLevel) String() string {
	switch l {
	case TLSHIdentical:
		return "identical"
	case TLSHNearlySame:
		return "nearly_same"
	case TLSHVerySimilar:
		return "very_similar"
	case TLSHSimilar:
		return "similar"
	case TLSHSomewhatSimilar:
		return "somewhat_similar"
	case TLSHDifferent:
		return "different"
	default:
		return "unknown"
	}
}

// ClassifyDistance categorizes a TLSH distance into similarity levels
func ClassifyDistance(distance int) TLSHSimilarityLevel {
	switch {
	case distance == 0:
		return TLSHIdentical
	case distance <= 10:
		return TLSHNearlySame
	case distance <= 30:
		return TLSHVerySimilar
	case distance <= 100:
		return TLSHSimilar
	case distance <= 200:
		return TLSHSomewhatSimilar
	default:
		return TLSHDifferent
	}
}

// --- Convenience Functions ---

// ComputeTLSH computes TLSH hash for content
func ComputeTLSH(content []byte) (*TLSHHash, error) {
	analyzer := NewTLSHAnalyzer(nil)
	return analyzer.ComputeHash(content)
}

// CompareTLSH compares two content byte slices and returns the distance
func CompareTLSH(content1, content2 []byte) (int, error) {
	analyzer := NewTLSHAnalyzer(nil)
	result, err := analyzer.CompareContents(content1, content2)
	if err != nil {
		return -1, err
	}
	return result.Distance, nil
}

// TLSHSimilarity calculates similarity percentage between two contents
func TLSHSimilarity(content1, content2 []byte) (float64, error) {
	analyzer := NewTLSHAnalyzer(nil)
	result, err := analyzer.CompareContents(content1, content2)
	if err != nil {
		return 0, err
	}
	return result.Similarity, nil
}
