package analyzer

import (
	"strings"
	"testing"
)

func TestTLSHAnalyzer_ComputeHash(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	// Content must be at least 50 bytes
	content := strings.Repeat("The quick brown fox jumps over the lazy dog. ", 5)

	hash, err := analyzer.ComputeHashString(content)
	if err != nil {
		t.Fatalf("Failed to compute hash: %v", err)
	}

	if hash == nil || hash.String() == "" {
		t.Error("Expected non-empty hash")
	}

	t.Logf("TLSH Hash: %s", hash.String())
}

func TestTLSHAnalyzer_ComputeHash_TooSmall(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	// Content too small
	content := "too small"

	_, err := analyzer.ComputeHashString(content)
	if err == nil {
		t.Error("Expected error for small content")
	}
}

func TestTLSHAnalyzer_IdenticalContent(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	content := strings.Repeat("The quick brown fox jumps over the lazy dog. ", 10)

	hash1, err := analyzer.ComputeHashString(content)
	if err != nil {
		t.Fatalf("Failed to compute hash1: %v", err)
	}

	hash2, err := analyzer.ComputeHashString(content)
	if err != nil {
		t.Fatalf("Failed to compute hash2: %v", err)
	}

	result := analyzer.CompareHashes(hash1, hash2)

	if result.Distance != 0 {
		t.Errorf("Expected distance 0 for identical content, got %d", result.Distance)
	}

	if result.Similarity != 100.0 {
		t.Errorf("Expected 100%% similarity, got %.2f%%", result.Similarity)
	}

	if !result.IsHighlySimilar {
		t.Error("Expected IsHighlySimilar to be true")
	}
}

func TestTLSHAnalyzer_SimilarContent(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	content1 := strings.Repeat("The quick brown fox jumps over the lazy dog. ", 10)
	content2 := strings.Repeat("The quick brown cat jumps over the lazy dog. ", 10)

	result, err := analyzer.CompareContents([]byte(content1), []byte(content2))
	if err != nil {
		t.Fatalf("Failed to compare: %v", err)
	}

	t.Logf("Distance: %d, Similarity: %.2f%%", result.Distance, result.Similarity)

	// Similar content should have low distance
	if result.Distance > 100 {
		t.Errorf("Expected low distance for similar content, got %d", result.Distance)
	}

	if !result.IsSimilar {
		t.Error("Expected IsSimilar to be true for similar content")
	}
}

func TestTLSHAnalyzer_DifferentContent(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	content1 := strings.Repeat("The quick brown fox jumps over the lazy dog. ", 10)
	content2 := strings.Repeat("Lorem ipsum dolor sit amet consectetur adipiscing elit. ", 10)

	result, err := analyzer.CompareContents([]byte(content1), []byte(content2))
	if err != nil {
		t.Fatalf("Failed to compare: %v", err)
	}

	t.Logf("Distance: %d, Similarity: %.2f%%", result.Distance, result.Similarity)

	// Very different content should have high distance
	if result.Distance < 50 {
		t.Errorf("Expected high distance for different content, got %d", result.Distance)
	}
}

func TestTLSHAnalyzer_Baseline(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	baseline := strings.Repeat("This is the baseline content for testing purposes. ", 5)
	current := strings.Repeat("This is the current content for testing purposes. ", 5)

	err := analyzer.SetBaselineFromContent([]byte(baseline))
	if err != nil {
		t.Fatalf("Failed to set baseline: %v", err)
	}

	if !analyzer.HasBaseline() {
		t.Error("Expected HasBaseline to return true")
	}

	result, err := analyzer.CompareString(current)
	if err != nil {
		t.Fatalf("Failed to compare: %v", err)
	}

	t.Logf("Baseline comparison - Distance: %d, Similarity: %.2f%%", result.Distance, result.Similarity)
}

func TestClassifyDistance(t *testing.T) {
	tests := []struct {
		distance int
		expected TLSHSimilarityLevel
	}{
		{0, TLSHIdentical},
		{5, TLSHNearlySame},
		{10, TLSHNearlySame},
		{20, TLSHVerySimilar},
		{30, TLSHVerySimilar},
		{50, TLSHSimilar},
		{100, TLSHSimilar},
		{150, TLSHSomewhatSimilar},
		{200, TLSHSomewhatSimilar},
		{250, TLSHDifferent},
	}

	for _, tt := range tests {
		t.Run(tt.expected.String(), func(t *testing.T) {
			level := ClassifyDistance(tt.distance)
			if level != tt.expected {
				t.Errorf("Distance %d: expected %s, got %s", tt.distance, tt.expected, level)
			}
		})
	}
}

func TestTLSHHash_Distance(t *testing.T) {
	analyzer := NewTLSHAnalyzer(nil)

	content := strings.Repeat("Test content for hash distance measurement. ", 10)

	hash1, _ := analyzer.ComputeHashString(content)
	hash2, _ := analyzer.ComputeHashString(content)

	distance := hash1.Distance(hash2)
	if distance != 0 {
		t.Errorf("Expected distance 0, got %d", distance)
	}

	similarity := hash1.Similarity(hash2)
	if similarity != 100.0 {
		t.Errorf("Expected 100%% similarity, got %.2f%%", similarity)
	}
}

func TestTLSHHash_NilHandling(t *testing.T) {
	var nilHash *TLSHHash

	if nilHash.String() != "" {
		t.Error("Expected empty string for nil hash")
	}

	analyzer := NewTLSHAnalyzer(nil)
	content := strings.Repeat("Test content. ", 10)
	hash, _ := analyzer.ComputeHashString(content)

	distance := hash.Distance(nilHash)
	if distance != -1 {
		t.Errorf("Expected -1 for nil comparison, got %d", distance)
	}

	similarity := hash.Similarity(nilHash)
	if similarity != 0 {
		t.Errorf("Expected 0%% similarity for nil, got %.2f%%", similarity)
	}
}

func TestConvenienceFunctions(t *testing.T) {
	content1 := []byte(strings.Repeat("Hello world this is a test. ", 10))
	content2 := []byte(strings.Repeat("Hello world this is a test. ", 10))

	// Test ComputeTLSH
	hash, err := ComputeTLSH(content1)
	if err != nil {
		t.Fatalf("ComputeTLSH failed: %v", err)
	}
	if hash.String() == "" {
		t.Error("Expected non-empty hash")
	}

	// Test CompareTLSH
	distance, err := CompareTLSH(content1, content2)
	if err != nil {
		t.Fatalf("CompareTLSH failed: %v", err)
	}
	if distance != 0 {
		t.Errorf("Expected distance 0, got %d", distance)
	}

	// Test TLSHSimilarity
	similarity, err := TLSHSimilarity(content1, content2)
	if err != nil {
		t.Fatalf("TLSHSimilarity failed: %v", err)
	}
	if similarity != 100.0 {
		t.Errorf("Expected 100%% similarity, got %.2f%%", similarity)
	}
}

func BenchmarkTLSHAnalyzer_ComputeHash(b *testing.B) {
	analyzer := NewTLSHAnalyzer(nil)
	content := []byte(strings.Repeat("Benchmark content for TLSH hash computation. ", 100))

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = analyzer.ComputeHash(content)
	}
}

func BenchmarkTLSHAnalyzer_Compare(b *testing.B) {
	analyzer := NewTLSHAnalyzer(nil)
	content1 := []byte(strings.Repeat("First content for comparison. ", 50))
	content2 := []byte(strings.Repeat("Second content for comparison. ", 50))

	hash1, _ := analyzer.ComputeHash(content1)
	hash2, _ := analyzer.ComputeHash(content2)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		analyzer.CompareHashes(hash1, hash2)
	}
}
