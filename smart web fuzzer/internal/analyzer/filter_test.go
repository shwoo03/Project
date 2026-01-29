package analyzer

import (
	"testing"
)

func TestStatusCodeFilter_Hide(t *testing.T) {
	filter := NewStatusCodeFilter(404, 500)

	tests := []struct {
		statusCode int
		filtered   bool
	}{
		{200, false},
		{201, false},
		{404, true},
		{500, true},
		{503, false},
	}

	for _, tt := range tests {
		input := &FilterInput{StatusCode: tt.statusCode}
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("StatusCode %d: expected filtered=%v, got %v", tt.statusCode, tt.filtered, result.Filtered)
		}
	}
}

func TestStatusCodeFilter_Show(t *testing.T) {
	filter := NewStatusCodeShowFilter(200, 201)

	tests := []struct {
		statusCode int
		filtered   bool
	}{
		{200, false},
		{201, false},
		{404, true},
		{500, true},
	}

	for _, tt := range tests {
		input := &FilterInput{StatusCode: tt.statusCode}
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("StatusCode %d: expected filtered=%v, got %v", tt.statusCode, tt.filtered, result.Filtered)
		}
	}
}

func TestLengthFilter_Range(t *testing.T) {
	filter := NewLengthFilter(100, 1000)

	tests := []struct {
		length   int
		filtered bool
	}{
		{50, true},    // Too short
		{100, false},  // At min
		{500, false},  // In range
		{1000, false}, // At max
		{1500, true},  // Too long
	}

	for _, tt := range tests {
		input := &FilterInput{ContentLength: tt.length}
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Length %d: expected filtered=%v, got %v", tt.length, tt.filtered, result.Filtered)
		}
	}
}

func TestLengthFilter_Exact(t *testing.T) {
	filter := NewExactLengthFilter(100, 200, 300)

	tests := []struct {
		length   int
		filtered bool
	}{
		{100, true},
		{150, false},
		{200, true},
		{250, false},
		{300, true},
	}

	for _, tt := range tests {
		input := &FilterInput{ContentLength: tt.length}
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Length %d: expected filtered=%v, got %v", tt.length, tt.filtered, result.Filtered)
		}
	}
}

func TestWordCountFilter_Range(t *testing.T) {
	filter := NewWordCountFilter(10, 100)

	tests := []struct {
		body     string
		filtered bool
	}{
		{"one two three", true}, // 3 words, too few
		{"one two three four five six seven eight nine ten eleven", false}, // 11 words
		{"", true}, // 0 words
	}

	for _, tt := range tests {
		input := NewFilterInput(200, []byte(tt.body), nil)
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Body %q: expected filtered=%v, got %v (wordCount=%d)",
				tt.body[:min(len(tt.body), 20)], tt.filtered, result.Filtered, input.GetWordCount())
		}
	}
}

func TestWordCountFilter_Exact(t *testing.T) {
	filter := NewExactWordCountFilter(3, 5)

	tests := []struct {
		body     string
		filtered bool
	}{
		{"one two three", true},           // 3 words - filtered
		{"one two three four", false},     // 4 words - not filtered
		{"one two three four five", true}, // 5 words - filtered
	}

	for _, tt := range tests {
		input := NewFilterInput(200, []byte(tt.body), nil)
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Body %q: expected filtered=%v, got %v", tt.body, tt.filtered, result.Filtered)
		}
	}
}

func TestLineCountFilter(t *testing.T) {
	filter := NewLineCountFilter(2, 10)

	tests := []struct {
		body     string
		filtered bool
	}{
		{"single line", true},    // 1 line
		{"line1\nline2", false},  // 2 lines
		{"a\nb\nc\nd\ne", false}, // 5 lines
	}

	for _, tt := range tests {
		input := NewFilterInput(200, []byte(tt.body), nil)
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Body with %d lines: expected filtered=%v, got %v",
				input.GetLineCount(), tt.filtered, result.Filtered)
		}
	}
}

func TestRegexFilter_Hide(t *testing.T) {
	filter, err := NewRegexFilter(`error|not found`, "error_pattern")
	if err != nil {
		t.Fatalf("Failed to create filter: %v", err)
	}

	tests := []struct {
		body     string
		filtered bool
	}{
		{"Page not found", true},
		{"An error occurred", true},
		{"Success", false},
		{"Data loaded successfully", false},
	}

	for _, tt := range tests {
		input := NewFilterInput(200, []byte(tt.body), nil)
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Body %q: expected filtered=%v, got %v", tt.body, tt.filtered, result.Filtered)
		}
	}
}

func TestRegexFilter_Show(t *testing.T) {
	filter, err := NewRegexShowFilter(`success|ok`, "success_pattern")
	if err != nil {
		t.Fatalf("Failed to create filter: %v", err)
	}

	tests := []struct {
		body     string
		filtered bool
	}{
		{"Operation success", false}, // Match - show
		{"Result: ok", false},        // Match - show
		{"Error occurred", true},     // No match - hide
	}

	for _, tt := range tests {
		input := NewFilterInput(200, []byte(tt.body), nil)
		result := filter.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Body %q: expected filtered=%v, got %v", tt.body, tt.filtered, result.Filtered)
		}
	}
}

func TestFilterChain_Any(t *testing.T) {
	chain := NewFilterChain(FilterModeAny,
		NewStatusCodeFilter(404),
		NewExactLengthFilter(100),
	)

	tests := []struct {
		statusCode int
		length     int
		filtered   bool
	}{
		{200, 200, false}, // Neither filter triggers
		{404, 200, true},  // Status code triggers
		{200, 100, true},  // Length triggers
		{404, 100, true},  // Both trigger
	}

	for _, tt := range tests {
		input := &FilterInput{StatusCode: tt.statusCode, ContentLength: tt.length}
		result := chain.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Status=%d, Length=%d: expected filtered=%v, got %v",
				tt.statusCode, tt.length, tt.filtered, result.Filtered)
		}
	}
}

func TestFilterChain_All(t *testing.T) {
	chain := NewFilterChain(FilterModeAll,
		NewStatusCodeFilter(404),
		NewExactLengthFilter(100),
	)

	tests := []struct {
		statusCode int
		length     int
		filtered   bool
	}{
		{200, 200, false}, // Neither filter triggers
		{404, 200, false}, // Only status code triggers
		{200, 100, false}, // Only length triggers
		{404, 100, true},  // Both trigger - only case that filters
	}

	for _, tt := range tests {
		input := &FilterInput{StatusCode: tt.statusCode, ContentLength: tt.length}
		result := chain.Apply(input)
		if result.Filtered != tt.filtered {
			t.Errorf("Status=%d, Length=%d: expected filtered=%v, got %v",
				tt.statusCode, tt.length, tt.filtered, result.Filtered)
		}
	}
}

func TestFilterInput_LazyLoading(t *testing.T) {
	body := "Hello world, this is a test.\nSecond line here."
	input := NewFilterInput(200, []byte(body), nil)

	// Initially not computed
	if input.WordCount != 0 {
		t.Error("WordCount should be 0 initially (lazy)")
	}
	if input.LineCount != 0 {
		t.Error("LineCount should be 0 initially (lazy)")
	}

	// After calling getters
	wordCount := input.GetWordCount()
	lineCount := input.GetLineCount()

	if wordCount != 9 {
		t.Errorf("Expected 9 words, got %d", wordCount)
	}
	if lineCount != 2 {
		t.Errorf("Expected 2 lines, got %d", lineCount)
	}

	// Should be cached now
	if input.WordCount != 9 {
		t.Error("WordCount should be cached")
	}
}

func TestPresetFilters(t *testing.T) {
	errorFilter := DefaultErrorFilter()
	successFilter := DefaultSuccessFilter()
	interestingFilter := InterestingStatusFilter()

	// Error filter should hide 404, 500
	input404 := &FilterInput{StatusCode: 404}
	if !errorFilter.Apply(input404).Filtered {
		t.Error("ErrorFilter should filter 404")
	}

	// Success filter should only show 200, 201, 202, 204
	input200 := &FilterInput{StatusCode: 200}
	if successFilter.Apply(input200).Filtered {
		t.Error("SuccessFilter should not filter 200")
	}

	input500 := &FilterInput{StatusCode: 500}
	if !successFilter.Apply(input500).Filtered {
		t.Error("SuccessFilter should filter 500")
	}

	// Interesting filter
	input403 := &FilterInput{StatusCode: 403}
	if interestingFilter.Apply(input403).Filtered {
		t.Error("InterestingFilter should not filter 403")
	}
}

func BenchmarkWordCount(b *testing.B) {
	body := []byte("The quick brown fox jumps over the lazy dog. " +
		"Lorem ipsum dolor sit amet, consectetur adipiscing elit. " +
		"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.")

	input := NewFilterInput(200, body, nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		input.WordCount = 0 // Reset for benchmark
		input.GetWordCount()
	}
}

func BenchmarkFilterChain(b *testing.B) {
	chain := NewFilterChain(FilterModeAny,
		NewStatusCodeFilter(404, 500),
		NewLengthFilter(100, 10000),
		NewWordCountFilter(10, 1000),
	)

	body := []byte("The quick brown fox jumps over the lazy dog multiple times.")
	input := NewFilterInput(200, body, nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		chain.Apply(input)
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
