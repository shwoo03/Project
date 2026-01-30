package cache

import (
	"os"
	"testing"
	"time"
)

func TestMemoryCache(t *testing.T) {
	config := &MemoryCacheConfig{
		Capacity: 1024,
		TTL:      1 * time.Second,
	}
	cache := NewMemoryCache(config)

	// Test Set and Get
	cache.Set("key1", []byte("value1"))
	value, ok := cache.Get("key1")
	if !ok {
		t.Error("Expected to find key1")
	}
	if string(value) != "value1" {
		t.Errorf("Expected 'value1', got '%s'", string(value))
	}

	// Test cache miss
	_, ok = cache.Get("nonexistent")
	if ok {
		t.Error("Should not find nonexistent key")
	}

	stats := cache.GetStats()
	if stats.Hits != 1 {
		t.Errorf("Expected 1 hit, got %d", stats.Hits)
	}
	if stats.Misses != 1 {
		t.Errorf("Expected 1 miss, got %d", stats.Misses)
	}
}

func TestMemoryCache_TTL(t *testing.T) {
	config := &MemoryCacheConfig{
		Capacity: 1024,
		TTL:      50 * time.Millisecond,
	}
	cache := NewMemoryCache(config)

	cache.Set("key1", []byte("value1"))

	// Should exist immediately
	_, ok := cache.Get("key1")
	if !ok {
		t.Error("Key should exist before TTL")
	}

	// Wait for TTL
	time.Sleep(100 * time.Millisecond)

	// Should be expired
	_, ok = cache.Get("key1")
	if ok {
		t.Error("Key should have expired")
	}
}

func TestMemoryCache_LRU(t *testing.T) {
	config := &MemoryCacheConfig{
		Capacity: 50, // Small capacity
		TTL:      1 * time.Minute,
	}
	cache := NewMemoryCache(config)

	// Add items that exceed capacity
	cache.Set("key1", []byte("12345678901234567890")) // 20 bytes
	cache.Set("key2", []byte("12345678901234567890")) // 20 bytes
	cache.Set("key3", []byte("12345678901234567890")) // 20 bytes - should evict key1

	// key1 should be evicted
	_, ok := cache.Get("key1")
	if ok {
		t.Error("key1 should have been evicted")
	}

	// key3 should exist
	_, ok = cache.Get("key3")
	if !ok {
		t.Error("key3 should exist")
	}
}

func TestMemoryCache_Delete(t *testing.T) {
	cache := NewMemoryCache(nil)

	cache.Set("key1", []byte("value1"))
	deleted := cache.Delete("key1")
	if !deleted {
		t.Error("Delete should return true")
	}

	_, ok := cache.Get("key1")
	if ok {
		t.Error("Key should be deleted")
	}
}

func TestResponseCache(t *testing.T) {
	rc := NewResponseCache(nil)

	method := "GET"
	url := "http://example.com/api"
	body := []byte("request body")
	response := []byte("response data")

	rc.Set(method, url, body, response)

	cached, ok := rc.Get(method, url, body)
	if !ok {
		t.Error("Should find cached response")
	}
	if string(cached) != string(response) {
		t.Error("Cached response mismatch")
	}

	// Different request should miss
	_, ok = rc.Get("POST", url, body)
	if ok {
		t.Error("Should not find different request")
	}
}

func TestBaselineCache(t *testing.T) {
	bc := NewBaselineCache()

	baseline := &BaselineEntry{
		URL:           "http://example.com",
		StatusCode:    200,
		ContentHash:   "abc123",
		ContentLength: 100,
		ResponseTime:  50 * time.Millisecond,
	}

	bc.Set("http://example.com", baseline)

	// Test no change
	diff := bc.Compare("http://example.com", 200, "abc123", 100, 50*time.Millisecond)
	if diff.HasChanges() {
		t.Error("Should not detect changes for identical response")
	}

	// Test status change
	diff = bc.Compare("http://example.com", 500, "abc123", 100, 50*time.Millisecond)
	if !diff.StatusChanged {
		t.Error("Should detect status change")
	}

	// Test content change
	diff = bc.Compare("http://example.com", 200, "def456", 100, 50*time.Millisecond)
	if !diff.ContentChanged {
		t.Error("Should detect content change")
	}
}

func TestDiskCache(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "cache_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	config := &DiskCacheConfig{
		BaseDir: tempDir,
		MaxSize: 10240,
		TTL:     1 * time.Hour,
	}

	cache, err := NewDiskCache(config)
	if err != nil {
		t.Fatalf("Failed to create disk cache: %v", err)
	}

	// Test Set and Get
	err = cache.Set("key1", []byte("value1"), 1*time.Hour)
	if err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	value, ok := cache.Get("key1")
	if !ok {
		t.Error("Expected to find key1")
	}
	if string(value) != "value1" {
		t.Errorf("Expected 'value1', got '%s'", string(value))
	}

	// Test Delete
	cache.Delete("key1")
	_, ok = cache.Get("key1")
	if ok {
		t.Error("Key should be deleted")
	}
}

func TestSimHash(t *testing.T) {
	sh := NewSimHash(64)

	data1 := []byte("The quick brown fox jumps over the lazy dog")
	data2 := []byte("The quick brown fox jumps over the lazy cat")
	data3 := []byte("Completely different content here")

	hash1 := sh.Hash(data1)
	hash2 := sh.Hash(data2)
	hash3 := sh.Hash(data3)

	// Similar content should have high similarity
	sim12 := sh.Similarity(hash1, hash2)
	if sim12 < 0.7 {
		t.Errorf("Expected high similarity, got %f", sim12)
	}

	// Different content should have lower similarity than similar content
	sim13 := sh.Similarity(hash1, hash3)
	if sim13 >= sim12 {
		t.Errorf("Different content should have lower similarity: %f vs %f", sim13, sim12)
	}
}

func TestMinHash(t *testing.T) {
	mh := NewMinHash(128)

	data1 := []byte("The quick brown fox jumps over the lazy dog")
	data2 := []byte("The quick brown fox jumps over the lazy cat")

	sig1 := mh.Signature(data1)
	sig2 := mh.Signature(data2)

	if len(sig1) != 128 {
		t.Errorf("Expected 128 hashes, got %d", len(sig1))
	}

	similarity := mh.EstimateSimilarity(sig1, sig2)
	if similarity < 0.5 {
		t.Errorf("Expected reasonable similarity, got %f", similarity)
	}
}

func TestSimilarityCache(t *testing.T) {
	sc := NewSimilarityCache(0.8)

	data1 := []byte("This is a test document about cats and dogs")
	data2 := []byte("This is a test document about cats and birds")
	data3 := []byte("Completely unrelated content")

	sc.Add("doc1", data1, nil)
	sc.Add("doc2", data2, nil)
	sc.Add("doc3", data3, nil)

	// Similar documents should be found
	similar := sc.FindSimilar([]byte("This is a test document about cats"))
	t.Logf("Found %d similar items", len(similar))

	stats := sc.GetStats()
	if stats["items"].(int) != 3 {
		t.Errorf("Expected 3 items, got %v", stats["items"])
	}
}

func TestDeduplicationCache(t *testing.T) {
	dc := NewDeduplicationCache()

	data1 := []byte("unique content 1")
	data2 := []byte("unique content 2")
	data3 := []byte("unique content 1") // Duplicate of data1

	// First add should succeed
	if !dc.Add("key1", data1) {
		t.Error("First add should succeed")
	}

	// Second add with different content should succeed
	if !dc.Add("key2", data2) {
		t.Error("Second add should succeed")
	}

	// Third add with duplicate content should fail
	if dc.Add("key3", data3) {
		t.Error("Duplicate add should fail")
	}

	// IsDuplicate should detect duplicate
	if !dc.IsDuplicate(data3) {
		t.Error("Should detect duplicate")
	}
}

func TestLSHIndex(t *testing.T) {
	idx := NewLSHIndex(20, 5)

	// Insert documents
	docs := map[string]string{
		"doc1": "The quick brown fox jumps over the lazy dog",
		"doc2": "The quick brown fox jumps over the lazy cat",
		"doc3": "A completely different document about programming",
		"doc4": "Another document about software development",
	}

	for key, content := range docs {
		idx.Insert(key, []byte(content))
	}

	// Query similar to doc1
	results := idx.Query([]byte("The quick brown fox"))
	t.Logf("Query results: %v", results)

	// Should find some results (LSH is probabilistic)
	t.Logf("Found %d results", len(results))
}

func TestContentFingerprint(t *testing.T) {
	data := []byte("test content")
	fp1 := GenerateFingerprint(data)
	fp2 := GenerateFingerprint(data)

	if !fp1.Equals(fp2) {
		t.Error("Same content should produce equal fingerprints")
	}

	fp3 := GenerateFingerprint([]byte("different content"))
	if fp1.Equals(fp3) {
		t.Error("Different content should produce different fingerprints")
	}
}

func BenchmarkMemoryCache(b *testing.B) {
	cache := NewMemoryCache(nil)

	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			key := string(rune(i % 100))
			if i%2 == 0 {
				cache.Set(key, []byte("value"))
			} else {
				cache.Get(key)
			}
			i++
		}
	})
}

func BenchmarkSimHash(b *testing.B) {
	sh := NewSimHash(64)
	data := []byte("The quick brown fox jumps over the lazy dog")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sh.Hash(data)
	}
}
