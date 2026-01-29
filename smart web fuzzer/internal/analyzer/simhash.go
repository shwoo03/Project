// Package analyzer provides SimHash implementation for structural similarity detection.
package analyzer

import (
	"hash/fnv"
	"regexp"
	"strings"
	"unicode"
)

const (
	// SimHashBits is the number of bits in the SimHash
	SimHashBits = 64
)

// SimHash represents a locality-sensitive hash for detecting similar content
type SimHash uint64

// SimHasher computes SimHash values for content comparison
type SimHasher struct {
	// Configuration
	nGramSize      int
	caseSensitive  bool
	stripHTML      bool
	ignoreNumbers  bool
	ignorePatterns []*regexp.Regexp
}

// SimHasherOption is a functional option for SimHasher configuration
type SimHasherOption func(*SimHasher)

// WithNGramSize sets the n-gram size for tokenization
func WithNGramSize(n int) SimHasherOption {
	return func(s *SimHasher) {
		if n > 0 {
			s.nGramSize = n
		}
	}
}

// WithCaseSensitive enables case-sensitive comparison
func WithCaseSensitive(enabled bool) SimHasherOption {
	return func(s *SimHasher) {
		s.caseSensitive = enabled
	}
}

// WithStripHTML enables HTML tag stripping
func WithStripHTML(enabled bool) SimHasherOption {
	return func(s *SimHasher) {
		s.stripHTML = enabled
	}
}

// WithIgnoreNumbers enables ignoring numeric values
func WithIgnoreNumbers(enabled bool) SimHasherOption {
	return func(s *SimHasher) {
		s.ignoreNumbers = enabled
	}
}

// WithIgnorePatterns adds regex patterns to ignore during comparison
func WithIgnorePatterns(patterns []string) SimHasherOption {
	return func(s *SimHasher) {
		for _, p := range patterns {
			if re, err := regexp.Compile(p); err == nil {
				s.ignorePatterns = append(s.ignorePatterns, re)
			}
		}
	}
}

// NewSimHasher creates a new SimHasher with the given options
func NewSimHasher(opts ...SimHasherOption) *SimHasher {
	s := &SimHasher{
		nGramSize:      3,
		caseSensitive:  false,
		stripHTML:      true,
		ignoreNumbers:  true,
		ignorePatterns: make([]*regexp.Regexp, 0),
	}

	// Add default patterns to ignore (timestamps, tokens, etc.)
	defaultPatterns := []string{
		`\d{4}-\d{2}-\d{2}`,  // Date: 2024-01-30
		`\d{2}:\d{2}:\d{2}`,  // Time: 12:34:56
		`[a-f0-9]{32}`,       // MD5 hash
		`[a-f0-9]{40}`,       // SHA1 hash
		`[a-f0-9]{64}`,       // SHA256 hash
		`[A-Za-z0-9_-]{20,}`, // Long tokens/IDs
		`csrf[_-]?token["\s:=]+["']?[^"'\s<>]+["']?`, // CSRF tokens
	}
	for _, p := range defaultPatterns {
		if re, err := regexp.Compile(p); err == nil {
			s.ignorePatterns = append(s.ignorePatterns, re)
		}
	}

	for _, opt := range opts {
		opt(s)
	}

	return s
}

// Compute calculates the SimHash of the given content
func (s *SimHasher) Compute(content string) SimHash {
	// Preprocess content
	processed := s.preprocess(content)

	// Extract features (tokens/n-grams)
	features := s.extractFeatures(processed)

	if len(features) == 0 {
		return 0
	}

	// Compute SimHash
	return computeSimHash(features)
}

// ComputeFromHTML calculates the SimHash focusing on HTML structure
func (s *SimHasher) ComputeFromHTML(html string) SimHash {
	// Extract structural features from HTML
	features := ExtractHTMLStructure(html)

	if len(features) == 0 {
		return 0
	}

	return computeSimHash(features)
}

// preprocess normalizes the content before feature extraction
func (s *SimHasher) preprocess(content string) string {
	result := content

	// Strip HTML tags if enabled
	if s.stripHTML {
		result = stripHTMLTags(result)
	}

	// Apply ignore patterns
	for _, re := range s.ignorePatterns {
		result = re.ReplaceAllString(result, " ")
	}

	// Normalize whitespace
	result = normalizeWhitespace(result)

	// Case normalization
	if !s.caseSensitive {
		result = strings.ToLower(result)
	}

	// Remove numbers if enabled
	if s.ignoreNumbers {
		result = removeNumbers(result)
	}

	return result
}

// extractFeatures extracts n-gram features from the content
func (s *SimHasher) extractFeatures(content string) []string {
	// Split into words
	words := strings.Fields(content)

	if len(words) == 0 {
		return nil
	}

	// If fewer words than n-gram size, return words as features
	if len(words) < s.nGramSize {
		return words
	}

	// Generate n-grams
	features := make([]string, 0, len(words)-s.nGramSize+1)
	for i := 0; i <= len(words)-s.nGramSize; i++ {
		ngram := strings.Join(words[i:i+s.nGramSize], " ")
		features = append(features, ngram)
	}

	return features
}

// computeSimHash computes the SimHash from a list of features
func computeSimHash(features []string) SimHash {
	var vector [SimHashBits]int

	for _, feature := range features {
		hash := hashFeature(feature)
		for i := 0; i < SimHashBits; i++ {
			if hash&(1<<i) != 0 {
				vector[i]++
			} else {
				vector[i]--
			}
		}
	}

	var simhash SimHash
	for i := 0; i < SimHashBits; i++ {
		if vector[i] > 0 {
			simhash |= 1 << i
		}
	}

	return simhash
}

// hashFeature computes a 64-bit hash for a feature string
func hashFeature(s string) uint64 {
	h := fnv.New64a()
	h.Write([]byte(s))
	return h.Sum64()
}

// Distance calculates the Hamming distance between two SimHash values
// The result ranges from 0 (identical) to 64 (completely different)
func (h SimHash) Distance(other SimHash) int {
	diff := h ^ other
	count := 0
	for diff != 0 {
		count++
		diff &= diff - 1
	}
	return count
}

// Similarity returns the similarity percentage (0-100)
func (h SimHash) Similarity(other SimHash) float64 {
	distance := h.Distance(other)
	return (1.0 - float64(distance)/float64(SimHashBits)) * 100.0
}

// IsSimilar checks if two SimHash values are similar within the given threshold
// A typical threshold is 3-10 (lower = more similar required)
func (h SimHash) IsSimilar(other SimHash, threshold int) bool {
	return h.Distance(other) <= threshold
}

// ExtractHTMLStructure extracts structural features from HTML content
// This focuses on the DOM structure rather than content
func ExtractHTMLStructure(html string) []string {
	features := make([]string, 0)

	// Simple regex-based tag extraction (for performance)
	tagRe := regexp.MustCompile(`<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>`)
	matches := tagRe.FindAllStringSubmatch(html, -1)

	var path []string
	for _, match := range matches {
		isClosing := match[1] == "/"
		tagName := strings.ToLower(match[2])

		// Skip self-closing and inline tags
		if isSelfClosingTag(tagName) {
			continue
		}

		if isClosing {
			// Pop from path
			if len(path) > 0 {
				path = path[:len(path)-1]
			}
		} else {
			// Push to path and record feature
			path = append(path, tagName)
			feature := strings.Join(path, ">")
			features = append(features, feature)
		}
	}

	return features
}

// isSelfClosingTag checks if a tag is self-closing
func isSelfClosingTag(tag string) bool {
	selfClosing := map[string]bool{
		"br": true, "hr": true, "img": true, "input": true,
		"meta": true, "link": true, "area": true, "base": true,
		"col": true, "embed": true, "param": true, "source": true,
		"track": true, "wbr": true,
	}
	return selfClosing[tag]
}

// stripHTMLTags removes all HTML tags from content
func stripHTMLTags(content string) string {
	re := regexp.MustCompile(`<[^>]*>`)
	return re.ReplaceAllString(content, " ")
}

// normalizeWhitespace collapses multiple whitespace characters
func normalizeWhitespace(content string) string {
	re := regexp.MustCompile(`\s+`)
	return strings.TrimSpace(re.ReplaceAllString(content, " "))
}

// removeNumbers removes numeric digits from content
func removeNumbers(content string) string {
	var result strings.Builder
	result.Grow(len(content))

	for _, r := range content {
		if !unicode.IsDigit(r) {
			result.WriteRune(r)
		}
	}
	return result.String()
}

// CompareStructure compares two HTML documents structurally
// Returns the Hamming distance (0 = identical structure)
func CompareStructure(html1, html2 string) int {
	hasher := NewSimHasher()
	hash1 := hasher.ComputeFromHTML(html1)
	hash2 := hasher.ComputeFromHTML(html2)
	return hash1.Distance(hash2)
}

// CompareContent compares two text contents
// Returns the Hamming distance (0 = identical content)
func CompareContent(content1, content2 string) int {
	hasher := NewSimHasher(WithStripHTML(false))
	hash1 := hasher.Compute(content1)
	hash2 := hasher.Compute(content2)
	return hash1.Distance(hash2)
}

// StructuralSimilarity returns the structural similarity percentage (0-100)
func StructuralSimilarity(html1, html2 string) float64 {
	hasher := NewSimHasher()
	hash1 := hasher.ComputeFromHTML(html1)
	hash2 := hasher.ComputeFromHTML(html2)
	return hash1.Similarity(hash2)
}
