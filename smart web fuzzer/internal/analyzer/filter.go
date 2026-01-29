// Package analyzer provides response filtering functionality.
// Filters help reduce noise by excluding responses that match known patterns.
package analyzer

import (
	"regexp"
	"strings"
	"unicode"
)

// FilterResult represents the result of applying filters
type FilterResult struct {
	// Filtered indicates if the response should be filtered out
	Filtered bool

	// Reason describes why the response was filtered
	Reason string

	// FilterName is the name of the filter that triggered
	FilterName string

	// Details provides additional context
	Details map[string]interface{}
}

// NotFiltered returns a FilterResult indicating the response passed all filters
func NotFiltered() *FilterResult {
	return &FilterResult{Filtered: false}
}

// FilteredBy returns a FilterResult indicating the response was filtered
func FilteredBy(name, reason string) *FilterResult {
	return &FilterResult{
		Filtered:   true,
		FilterName: name,
		Reason:     reason,
		Details:    make(map[string]interface{}),
	}
}

// Filter defines the interface for response filters
type Filter interface {
	// Name returns the filter's identifier
	Name() string

	// Apply checks if the response should be filtered
	Apply(resp *FilterInput) *FilterResult
}

// FilterInput contains the data needed for filtering
type FilterInput struct {
	StatusCode    int
	Body          []byte
	BodyString    string // Lazy-loaded
	ContentLength int
	WordCount     int // Lazy-loaded
	LineCount     int // Lazy-loaded
	Headers       map[string]string
}

// NewFilterInput creates a FilterInput from response data
func NewFilterInput(statusCode int, body []byte, headers map[string]string) *FilterInput {
	return &FilterInput{
		StatusCode:    statusCode,
		Body:          body,
		ContentLength: len(body),
		Headers:       headers,
	}
}

// GetBodyString returns the body as string (lazy-loaded)
func (f *FilterInput) GetBodyString() string {
	if f.BodyString == "" && len(f.Body) > 0 {
		f.BodyString = string(f.Body)
	}
	return f.BodyString
}

// GetWordCount returns the word count (lazy-loaded)
func (f *FilterInput) GetWordCount() int {
	if f.WordCount == 0 && len(f.Body) > 0 {
		f.WordCount = countWords(f.GetBodyString())
	}
	return f.WordCount
}

// GetLineCount returns the line count (lazy-loaded)
func (f *FilterInput) GetLineCount() int {
	if f.LineCount == 0 && len(f.Body) > 0 {
		f.LineCount = strings.Count(f.GetBodyString(), "\n") + 1
	}
	return f.LineCount
}

// countWords counts words in a string
func countWords(s string) int {
	count := 0
	inWord := false
	for _, r := range s {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			if !inWord {
				inWord = true
				count++
			}
		} else {
			inWord = false
		}
	}
	return count
}

// --- Status Code Filter ---

// StatusCodeFilter filters responses based on status codes
type StatusCodeFilter struct {
	// HideCodes are status codes to filter out
	HideCodes map[int]bool

	// ShowCodes are the only status codes to show (if set, overrides HideCodes)
	ShowCodes map[int]bool
}

// NewStatusCodeFilter creates a filter that hides specific status codes
func NewStatusCodeFilter(hideCodes ...int) *StatusCodeFilter {
	hide := make(map[int]bool)
	for _, code := range hideCodes {
		hide[code] = true
	}
	return &StatusCodeFilter{HideCodes: hide}
}

// NewStatusCodeShowFilter creates a filter that only shows specific status codes
func NewStatusCodeShowFilter(showCodes ...int) *StatusCodeFilter {
	show := make(map[int]bool)
	for _, code := range showCodes {
		show[code] = true
	}
	return &StatusCodeFilter{ShowCodes: show}
}

func (f *StatusCodeFilter) Name() string {
	return "status_code"
}

func (f *StatusCodeFilter) Apply(input *FilterInput) *FilterResult {
	// Show mode: only show specific codes
	if len(f.ShowCodes) > 0 {
		if !f.ShowCodes[input.StatusCode] {
			return FilteredBy(f.Name(), "status code not in show list")
		}
		return NotFiltered()
	}

	// Hide mode: hide specific codes
	if f.HideCodes[input.StatusCode] {
		return FilteredBy(f.Name(), "status code in hide list")
	}

	return NotFiltered()
}

// --- Content Length Filter ---

// LengthFilter filters responses based on content length
type LengthFilter struct {
	// MinLength is the minimum length (exclusive)
	MinLength int

	// MaxLength is the maximum length (exclusive), 0 means no max
	MaxLength int

	// ExactLengths are specific lengths to filter
	ExactLengths map[int]bool

	// HideExact determines whether to hide or show exact lengths
	HideExact bool
}

// NewLengthFilter creates a filter for length range
func NewLengthFilter(minLength, maxLength int) *LengthFilter {
	return &LengthFilter{
		MinLength:    minLength,
		MaxLength:    maxLength,
		ExactLengths: make(map[int]bool),
	}
}

// NewExactLengthFilter creates a filter that hides specific lengths
func NewExactLengthFilter(lengths ...int) *LengthFilter {
	exact := make(map[int]bool)
	for _, l := range lengths {
		exact[l] = true
	}
	return &LengthFilter{
		ExactLengths: exact,
		HideExact:    true,
	}
}

func (f *LengthFilter) Name() string {
	return "length"
}

func (f *LengthFilter) Apply(input *FilterInput) *FilterResult {
	length := input.ContentLength

	// Check exact lengths
	if len(f.ExactLengths) > 0 {
		if f.ExactLengths[length] {
			if f.HideExact {
				result := FilteredBy(f.Name(), "exact length match")
				result.Details["length"] = length
				return result
			}
		} else if !f.HideExact {
			return FilteredBy(f.Name(), "length not in show list")
		}
	}

	// Check range
	if f.MinLength > 0 && length < f.MinLength {
		result := FilteredBy(f.Name(), "length below minimum")
		result.Details["length"] = length
		result.Details["min"] = f.MinLength
		return result
	}

	if f.MaxLength > 0 && length > f.MaxLength {
		result := FilteredBy(f.Name(), "length above maximum")
		result.Details["length"] = length
		result.Details["max"] = f.MaxLength
		return result
	}

	return NotFiltered()
}

// --- Word Count Filter ---

// WordCountFilter filters responses based on word count
type WordCountFilter struct {
	// MinWords is the minimum word count
	MinWords int

	// MaxWords is the maximum word count, 0 means no max
	MaxWords int

	// ExactCounts are specific word counts to filter
	ExactCounts map[int]bool

	// HideExact determines whether to hide or show exact counts
	HideExact bool
}

// NewWordCountFilter creates a filter for word count range
func NewWordCountFilter(minWords, maxWords int) *WordCountFilter {
	return &WordCountFilter{
		MinWords:    minWords,
		MaxWords:    maxWords,
		ExactCounts: make(map[int]bool),
	}
}

// NewExactWordCountFilter creates a filter that hides specific word counts
func NewExactWordCountFilter(counts ...int) *WordCountFilter {
	exact := make(map[int]bool)
	for _, c := range counts {
		exact[c] = true
	}
	return &WordCountFilter{
		ExactCounts: exact,
		HideExact:   true,
	}
}

func (f *WordCountFilter) Name() string {
	return "word_count"
}

func (f *WordCountFilter) Apply(input *FilterInput) *FilterResult {
	wordCount := input.GetWordCount()

	// Check exact counts
	if len(f.ExactCounts) > 0 {
		if f.ExactCounts[wordCount] {
			if f.HideExact {
				result := FilteredBy(f.Name(), "exact word count match")
				result.Details["word_count"] = wordCount
				return result
			}
		} else if !f.HideExact {
			return FilteredBy(f.Name(), "word count not in show list")
		}
	}

	// Check range
	if f.MinWords > 0 && wordCount < f.MinWords {
		result := FilteredBy(f.Name(), "word count below minimum")
		result.Details["word_count"] = wordCount
		result.Details["min"] = f.MinWords
		return result
	}

	if f.MaxWords > 0 && wordCount > f.MaxWords {
		result := FilteredBy(f.Name(), "word count above maximum")
		result.Details["word_count"] = wordCount
		result.Details["max"] = f.MaxWords
		return result
	}

	return NotFiltered()
}

// --- Line Count Filter ---

// LineCountFilter filters responses based on line count
type LineCountFilter struct {
	MinLines    int
	MaxLines    int
	ExactCounts map[int]bool
	HideExact   bool
}

// NewLineCountFilter creates a filter for line count range
func NewLineCountFilter(minLines, maxLines int) *LineCountFilter {
	return &LineCountFilter{
		MinLines:    minLines,
		MaxLines:    maxLines,
		ExactCounts: make(map[int]bool),
	}
}

// NewExactLineCountFilter creates a filter that hides specific line counts
func NewExactLineCountFilter(counts ...int) *LineCountFilter {
	exact := make(map[int]bool)
	for _, c := range counts {
		exact[c] = true
	}
	return &LineCountFilter{
		ExactCounts: exact,
		HideExact:   true,
	}
}

func (f *LineCountFilter) Name() string {
	return "line_count"
}

func (f *LineCountFilter) Apply(input *FilterInput) *FilterResult {
	lineCount := input.GetLineCount()

	// Check exact counts
	if len(f.ExactCounts) > 0 {
		if f.ExactCounts[lineCount] {
			if f.HideExact {
				result := FilteredBy(f.Name(), "exact line count match")
				result.Details["line_count"] = lineCount
				return result
			}
		} else if !f.HideExact {
			return FilteredBy(f.Name(), "line count not in show list")
		}
	}

	// Check range
	if f.MinLines > 0 && lineCount < f.MinLines {
		return FilteredBy(f.Name(), "line count below minimum")
	}

	if f.MaxLines > 0 && lineCount > f.MaxLines {
		return FilteredBy(f.Name(), "line count above maximum")
	}

	return NotFiltered()
}

// --- Regex Filter ---

// RegexFilter filters responses based on regex pattern matching
type RegexFilter struct {
	Pattern     *regexp.Regexp
	PatternName string
	HideMatch   bool // true = hide matches, false = hide non-matches
}

// NewRegexFilter creates a filter that hides responses matching the pattern
func NewRegexFilter(pattern string, name string) (*RegexFilter, error) {
	re, err := regexp.Compile(pattern)
	if err != nil {
		return nil, err
	}
	return &RegexFilter{
		Pattern:     re,
		PatternName: name,
		HideMatch:   true,
	}, nil
}

// NewRegexShowFilter creates a filter that only shows responses matching the pattern
func NewRegexShowFilter(pattern string, name string) (*RegexFilter, error) {
	re, err := regexp.Compile(pattern)
	if err != nil {
		return nil, err
	}
	return &RegexFilter{
		Pattern:     re,
		PatternName: name,
		HideMatch:   false,
	}, nil
}

func (f *RegexFilter) Name() string {
	return "regex:" + f.PatternName
}

func (f *RegexFilter) Apply(input *FilterInput) *FilterResult {
	matches := f.Pattern.MatchString(input.GetBodyString())

	if f.HideMatch && matches {
		return FilteredBy(f.Name(), "pattern matched")
	}

	if !f.HideMatch && !matches {
		return FilteredBy(f.Name(), "pattern not matched")
	}

	return NotFiltered()
}

// --- Filter Chain ---

// FilterChain combines multiple filters
type FilterChain struct {
	filters []Filter
	mode    FilterMode
}

// FilterMode determines how multiple filters are combined
type FilterMode int

const (
	// FilterModeAny filters if ANY filter triggers (OR logic)
	FilterModeAny FilterMode = iota

	// FilterModeAll filters only if ALL filters trigger (AND logic)
	FilterModeAll
)

// NewFilterChain creates a new filter chain
func NewFilterChain(mode FilterMode, filters ...Filter) *FilterChain {
	return &FilterChain{
		filters: filters,
		mode:    mode,
	}
}

// Add adds a filter to the chain
func (fc *FilterChain) Add(f Filter) {
	fc.filters = append(fc.filters, f)
}

// Apply applies all filters in the chain
func (fc *FilterChain) Apply(input *FilterInput) *FilterResult {
	if len(fc.filters) == 0 {
		return NotFiltered()
	}

	var results []*FilterResult
	filteredCount := 0

	for _, f := range fc.filters {
		result := f.Apply(input)
		results = append(results, result)
		if result.Filtered {
			filteredCount++

			// Short-circuit for ANY mode
			if fc.mode == FilterModeAny {
				return result
			}
		} else {
			// Short-circuit for ALL mode
			if fc.mode == FilterModeAll {
				return NotFiltered()
			}
		}
	}

	// For ALL mode, all must be filtered
	if fc.mode == FilterModeAll && filteredCount == len(fc.filters) {
		return FilteredBy("chain", "all filters triggered")
	}

	return NotFiltered()
}

// Filters returns the list of filters in the chain
func (fc *FilterChain) Filters() []Filter {
	return fc.filters
}

// --- Preset Filters ---

// DefaultErrorFilter returns a filter that hides common error responses
func DefaultErrorFilter() *StatusCodeFilter {
	return NewStatusCodeFilter(404, 500, 502, 503, 504)
}

// DefaultSuccessFilter returns a filter that only shows success responses
func DefaultSuccessFilter() *StatusCodeFilter {
	return NewStatusCodeShowFilter(200, 201, 202, 204)
}

// InterestingStatusFilter returns a filter that shows potentially interesting status codes
func InterestingStatusFilter() *StatusCodeFilter {
	return NewStatusCodeShowFilter(200, 201, 301, 302, 400, 401, 403, 405, 500)
}
