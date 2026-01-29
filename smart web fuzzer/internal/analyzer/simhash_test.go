package analyzer

import (
	"strings"
	"testing"
)

func TestSimHasher_Compute(t *testing.T) {
	hasher := NewSimHasher()

	// Identical content should produce identical hash
	content1 := "The quick brown fox jumps over the lazy dog"
	content2 := "The quick brown fox jumps over the lazy dog"

	hash1 := hasher.Compute(content1)
	hash2 := hasher.Compute(content2)

	if hash1 != hash2 {
		t.Errorf("Identical content should produce identical hash: %v != %v", hash1, hash2)
	}
}

func TestSimHasher_SimilarContent(t *testing.T) {
	hasher := NewSimHasher()

	// Similar content should produce similar hash
	content1 := "The quick brown fox jumps over the lazy dog"
	content2 := "The quick brown fox leaps over the lazy dog"

	hash1 := hasher.Compute(content1)
	hash2 := hasher.Compute(content2)

	distance := hash1.Distance(hash2)
	if distance > 20 {
		t.Errorf("Similar content should have low distance, got %d", distance)
	}
}

func TestSimHasher_DifferentContent(t *testing.T) {
	hasher := NewSimHasher()

	// Very different content should produce different hash
	content1 := "The quick brown fox jumps over the lazy dog"
	content2 := "Lorem ipsum dolor sit amet consectetur adipiscing elit"

	hash1 := hasher.Compute(content1)
	hash2 := hasher.Compute(content2)

	distance := hash1.Distance(hash2)
	if distance < 10 {
		t.Errorf("Different content should have high distance, got %d", distance)
	}
}

func TestSimHash_Distance(t *testing.T) {
	tests := []struct {
		name     string
		hash1    SimHash
		hash2    SimHash
		expected int
	}{
		{"identical", 0xFFFF, 0xFFFF, 0},
		{"one bit", 0xFFFE, 0xFFFF, 1},
		{"four bits", 0xFFF0, 0xFFFF, 4},
		{"all different", 0x0000, 0xFFFF, 16},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			distance := tt.hash1.Distance(tt.hash2)
			if distance != tt.expected {
				t.Errorf("Expected distance %d, got %d", tt.expected, distance)
			}
		})
	}
}

func TestSimHash_Similarity(t *testing.T) {
	// Identical should be 100%
	var hash1 SimHash = 0xFFFFFFFFFFFFFFFF
	var hash2 SimHash = 0xFFFFFFFFFFFFFFFF

	similarity := hash1.Similarity(hash2)
	if similarity != 100.0 {
		t.Errorf("Expected 100%% similarity, got %.2f%%", similarity)
	}

	// Completely different should be 0%
	hash3 := SimHash(0)
	similarity = hash1.Similarity(hash3)
	if similarity != 0.0 {
		t.Errorf("Expected 0%% similarity, got %.2f%%", similarity)
	}
}

func TestSimHash_IsSimilar(t *testing.T) {
	var hash1 SimHash = 0xFFFFFFFFFFFFFFFF
	var hash2 SimHash = 0xFFFFFFFFFFFFFFF0 // 4 bits different

	if !hash1.IsSimilar(hash2, 5) {
		t.Error("Expected hashes to be similar with threshold 5")
	}

	if hash1.IsSimilar(hash2, 3) {
		t.Error("Expected hashes to NOT be similar with threshold 3")
	}
}

func TestExtractHTMLStructure(t *testing.T) {
	html := `<html><body><div><p>Hello</p><p>World</p></div></body></html>`
	features := ExtractHTMLStructure(html)

	expectedFeatures := []string{
		"html",
		"html>body",
		"html>body>div",
		"html>body>div>p",
		"html>body>div>p",
	}

	if len(features) != len(expectedFeatures) {
		t.Errorf("Expected %d features, got %d", len(expectedFeatures), len(features))
	}

	for i, expected := range expectedFeatures {
		if i < len(features) && features[i] != expected {
			t.Errorf("Feature %d: expected %s, got %s", i, expected, features[i])
		}
	}
}

func TestSimHasher_ComputeFromHTML(t *testing.T) {
	hasher := NewSimHasher()

	// Same structure, different content
	html1 := `<html><body><div><p>Hello World</p></div></body></html>`
	html2 := `<html><body><div><p>Goodbye Universe</p></div></body></html>`

	hash1 := hasher.ComputeFromHTML(html1)
	hash2 := hasher.ComputeFromHTML(html2)

	// Structure is identical, so hashes should be identical
	if hash1 != hash2 {
		t.Errorf("Same structure should produce same hash: distance=%d", hash1.Distance(hash2))
	}

	// Different structure
	html3 := `<html><body><div><p>Hello</p><span>World</span></div></body></html>`
	hash3 := hasher.ComputeFromHTML(html3)

	if hash1.Distance(hash3) == 0 {
		t.Error("Different structure should produce different hash")
	}
}

func TestCompareStructure(t *testing.T) {
	html1 := `<html><body><div id="content"><h1>Title</h1><p>Paragraph 1</p><p>Paragraph 2</p></div></body></html>`
	html2 := `<html><body><div id="main"><h1>Different Title</h1><p>Other text</p><p>More text</p></div></body></html>`

	distance := CompareStructure(html1, html2)

	// Same structure, so distance should be 0
	if distance != 0 {
		t.Errorf("Same structure should have distance 0, got %d", distance)
	}
}

func TestStructuralSimilarity(t *testing.T) {
	html1 := `<html><body><div><p>Content</p></div></body></html>`
	html2 := `<html><body><div><p>Different</p></div></body></html>`

	similarity := StructuralSimilarity(html1, html2)

	if similarity != 100.0 {
		t.Errorf("Same structure should have 100%% similarity, got %.2f%%", similarity)
	}
}

func TestSimHasher_IgnorePatterns(t *testing.T) {
	hasher := NewSimHasher()

	// Content with timestamp
	content1 := "User logged in at 2024-01-30 12:34:56"
	content2 := "User logged in at 2024-02-15 09:00:00"

	hash1 := hasher.Compute(content1)
	hash2 := hasher.Compute(content2)

	// Timestamps should be ignored, so hashes should be similar
	distance := hash1.Distance(hash2)
	if distance > 10 {
		t.Errorf("Content with only timestamp difference should be similar, distance=%d", distance)
	}
}

func TestSimHasher_Options(t *testing.T) {
	// Test with case sensitivity
	hasher := NewSimHasher(WithCaseSensitive(true))

	content1 := "Hello World"
	content2 := "hello world"

	hash1 := hasher.Compute(content1)
	hash2 := hasher.Compute(content2)

	if hash1 == hash2 {
		t.Error("Case sensitive hasher should produce different hashes for different cases")
	}

	// Test without case sensitivity
	hasher2 := NewSimHasher(WithCaseSensitive(false))
	hash3 := hasher2.Compute(content1)
	hash4 := hasher2.Compute(content2)

	if hash3 != hash4 {
		t.Error("Case insensitive hasher should produce same hash for different cases")
	}
}

func TestSimHasher_NGramSize(t *testing.T) {
	hasher1 := NewSimHasher(WithNGramSize(2))
	hasher2 := NewSimHasher(WithNGramSize(5))

	content := "the quick brown fox jumps over the lazy dog"

	hash1 := hasher1.Compute(content)
	hash2 := hasher2.Compute(content)

	// Different n-gram sizes should produce different hashes
	if hash1 == hash2 {
		t.Error("Different n-gram sizes should produce different hashes")
	}
}

func BenchmarkSimHasher_Compute(b *testing.B) {
	hasher := NewSimHasher()
	content := strings.Repeat("The quick brown fox jumps over the lazy dog. ", 100)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		hasher.Compute(content)
	}
}

func BenchmarkSimHasher_ComputeFromHTML(b *testing.B) {
	hasher := NewSimHasher()
	html := `<html><head><title>Test</title></head><body>
		<div class="container">
			<header><h1>Title</h1></header>
			<main><p>Content</p><p>More content</p></main>
			<footer><p>Footer</p></footer>
		</div>
	</body></html>`

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		hasher.ComputeFromHTML(html)
	}
}

func BenchmarkSimHash_Distance(b *testing.B) {
	var hash1 SimHash = 0xABCDEF0123456789
	var hash2 SimHash = 0x123456789ABCDEF0

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		hash1.Distance(hash2)
	}
}
