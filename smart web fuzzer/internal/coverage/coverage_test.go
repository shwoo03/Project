package coverage

import (
	"context"
	"os"
	"testing"
	"time"
)

func TestCoverageMap(t *testing.T) {
	cm := NewCoverageMap(1024)

	// Test RecordEdge
	isNew := cm.RecordEdge(100, 200)
	if !isNew {
		t.Error("First edge should be new")
	}

	// Same edge again - may or may not be new depending on bucket change
	_ = cm.RecordEdge(100, 200)

	stats := cm.GetStats()
	if stats.EdgesCovered < 1 {
		t.Errorf("Expected at least 1 edge, got %d", stats.EdgesCovered)
	}
}

func TestCoverageMap_Merge(t *testing.T) {
	cm1 := NewCoverageMap(1024)
	cm2 := NewCoverageMap(1024)

	cm1.RecordEdge(100, 200)
	cm2.RecordEdge(300, 400)

	newEdges := cm1.Merge(cm2)
	if newEdges < 1 {
		t.Errorf("Expected at least 1 new edge, got %d", newEdges)
	}

	stats := cm1.GetStats()
	if stats.EdgesCovered < 2 {
		t.Errorf("Expected at least 2 edges after merge, got %d", stats.EdgesCovered)
	}
}

func TestCoverageMap_Clone(t *testing.T) {
	cm := NewCoverageMap(1024)
	cm.RecordEdge(100, 200)

	clone := cm.Clone()

	// Original and clone should have same stats
	origStats := cm.GetStats()
	cloneStats := clone.GetStats()

	if origStats.EdgesCovered != cloneStats.EdgesCovered {
		t.Error("Clone should have same coverage")
	}

	// Modifying clone shouldn't affect original
	clone.RecordEdge(300, 400)
	origStatsAfter := cm.GetStats()

	if origStatsAfter.EdgesCovered != origStats.EdgesCovered {
		t.Error("Modifying clone affected original")
	}
}

func TestCoverageTracker(t *testing.T) {
	tracker := NewCoverageTracker(1024)

	// Record some executions
	cm1 := NewCoverageMap(1024)
	cm1.RecordEdge(100, 200)
	isInteresting := tracker.RecordExecution(cm1, "hash1")
	if !isInteresting {
		t.Error("First execution should be interesting")
	}

	cm2 := NewCoverageMap(1024)
	cm2.RecordEdge(100, 200) // Same edge
	isInteresting = tracker.RecordExecution(cm2, "hash2")
	if isInteresting {
		t.Error("Same coverage should not be interesting")
	}

	cm3 := NewCoverageMap(1024)
	cm3.RecordEdge(300, 400) // New edge
	isInteresting = tracker.RecordExecution(cm3, "hash3")
	if !isInteresting {
		t.Error("New edge should be interesting")
	}

	if tracker.GetExecutionCount() != 3 {
		t.Errorf("Expected 3 executions, got %d", tracker.GetExecutionCount())
	}
}

func TestEdgeHasher(t *testing.T) {
	eh := NewEdgeHasher()

	// Hash some edges
	edge1 := eh.HashEdge(100)
	edge2 := eh.HashEdge(200)
	edge3 := eh.HashEdge(100) // Back to 100

	// Edges should be different
	if edge1 == edge2 {
		t.Error("Different blocks should produce different edges")
	}

	// Reset and re-hash
	eh.Reset()
	edge1Again := eh.HashEdge(100)
	if edge1 != edge1Again {
		t.Error("Same block from same state should produce same edge")
	}

	_ = edge3 // Used
}

func TestBlockID(t *testing.T) {
	id1 := BlockID("file1.go", 10)
	id2 := BlockID("file1.go", 20)
	id3 := BlockID("file2.go", 10)

	// Same file, different lines should produce different IDs
	if id1 == id2 {
		t.Error("Different lines should produce different block IDs")
	}

	// Different files should produce different IDs
	if id1 == id3 {
		t.Error("Different files should produce different block IDs")
	}
}

func TestCorpus(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "corpus_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	corpus := NewCorpus(tempDir)

	// Add entries
	entry1 := &CorpusEntry{
		Data: []byte("test input 1"),
		Hash: "hash1",
	}
	added := corpus.Add(entry1)
	if !added {
		t.Error("Should add new entry")
	}

	// Duplicate should not be added
	added = corpus.Add(entry1)
	if added {
		t.Error("Should not add duplicate")
	}

	if corpus.Size() != 1 {
		t.Errorf("Expected size 1, got %d", corpus.Size())
	}

	// Get entry
	retrieved := corpus.GetEntry("hash1")
	if retrieved == nil {
		t.Error("Should retrieve entry")
	}
}

func TestCorpus_Crashes(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "corpus_crash_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	corpus := NewCorpus(tempDir)

	result := &ExecutionResult{
		Crashed:  true,
		ExitCode: 1,
		Output:   []byte("crash output"),
	}

	added := corpus.AddCrash([]byte("crash input"), result)
	if !added {
		t.Error("Should add crash")
	}

	if corpus.CrashCount() != 1 {
		t.Errorf("Expected 1 crash, got %d", corpus.CrashCount())
	}

	// Duplicate crash should not be added
	added = corpus.AddCrash([]byte("crash input"), result)
	if added {
		t.Error("Should not add duplicate crash")
	}
}

func TestCorpus_Minimize(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "corpus_min_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	corpus := NewCorpus(tempDir)

	// Add multiple entries
	for i := 0; i < 10; i++ {
		entry := &CorpusEntry{
			Data: []byte{byte(i)},
			Hash: string(rune('a' + i)),
			Coverage: CoverageStats{
				EdgesCovered: i,
			},
		}
		corpus.Add(entry)
	}

	if corpus.Size() != 10 {
		t.Errorf("Expected 10 entries, got %d", corpus.Size())
	}

	removed := corpus.Minimize()
	t.Logf("Minimized: removed %d entries, %d remaining", removed, corpus.Size())
}

func TestCorpusStats(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "corpus_stats_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	corpus := NewCorpus(tempDir)

	corpus.Add(&CorpusEntry{Data: []byte("short"), Hash: "a", IsSeed: true})
	corpus.Add(&CorpusEntry{Data: []byte("longer input"), Hash: "b"})
	corpus.Add(&CorpusEntry{Data: []byte("x"), Hash: "c", Favored: true})

	stats := corpus.GetStats()
	if stats.EntryCount != 3 {
		t.Errorf("Expected 3 entries, got %d", stats.EntryCount)
	}
	if stats.Seeds != 1 {
		t.Errorf("Expected 1 seed, got %d", stats.Seeds)
	}
	if stats.Favored != 1 {
		t.Errorf("Expected 1 favored, got %d", stats.Favored)
	}
}

func TestFeedbackLoop(t *testing.T) {
	config := &FeedbackConfig{
		MaxExecutions:    10,
		Timeout:          5 * time.Second,
		BitmapSize:       1024,
		MutationsPerSeed: 2,
	}

	mutator := &testMutator{}
	executor := &testExecutor{}

	fl := NewFeedbackLoop(config, mutator, executor)

	// Add a seed
	fl.AddSeed([]byte("seed input"))

	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
	defer cancel()

	fl.Start(ctx)

	// Wait a bit
	time.Sleep(200 * time.Millisecond)

	stats := fl.GetStats()
	t.Logf("Feedback stats: %+v", stats)

	fl.Stop()
}

func TestInputScheduler(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "scheduler_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	scheduler := NewInputScheduler()
	corpus := NewCorpus(tempDir)

	// Empty corpus should return nil
	next := scheduler.Next(corpus)
	if next != nil {
		t.Error("Empty corpus should return nil")
	}

	// Add entries
	entry := &CorpusEntry{Data: []byte("test"), Hash: "hash1"}
	corpus.Add(entry)

	next = scheduler.Next(corpus)
	if next == nil {
		t.Error("Should return entry from corpus")
	}

	// Update priority
	entry.Coverage.EdgesCovered = 100
	scheduler.UpdatePriority(entry)
}

func TestContentHash(t *testing.T) {
	hash1 := ContentHash([]byte("test data"))
	hash2 := ContentHash([]byte("test data"))
	hash3 := ContentHash([]byte("different"))

	if hash1 != hash2 {
		t.Error("Same data should produce same hash")
	}

	if hash1 == hash3 {
		t.Error("Different data should produce different hash")
	}

	if len(hash1) != 64 {
		t.Errorf("Expected 64 char hash, got %d", len(hash1))
	}
}

func TestHitCountBucket(t *testing.T) {
	testCases := []struct {
		count    byte
		expected byte
	}{
		{0, 0},
		{1, 1},
		{2, 2},
		{3, 3},
		{4, 4},
		{7, 4},
		{8, 5},
		{15, 5},
		{16, 6},
		{31, 6},
		{32, 7},
		{127, 7},
		{128, 8},
		{255, 8},
	}

	for _, tc := range testCases {
		result := hitCountBucket(tc.count)
		if result != tc.expected {
			t.Errorf("hitCountBucket(%d) = %d, expected %d", tc.count, result, tc.expected)
		}
	}
}

// Test helpers

type testMutator struct{}

func (m *testMutator) Mutate(input []byte) []byte {
	// Simple mutation: flip a byte
	if len(input) == 0 {
		return []byte{0}
	}
	result := make([]byte, len(input))
	copy(result, input)
	result[0] ^= 0xff
	return result
}

type testExecutor struct {
	execCount int
}

func (e *testExecutor) Execute(ctx context.Context, input []byte) (*ExecutionResult, error) {
	e.execCount++

	cm := NewCoverageMap(1024)
	// Simulate some coverage based on input
	for i, b := range input {
		cm.RecordEdge(uint32(i), uint32(b))
	}

	return &ExecutionResult{
		Coverage: cm,
		Duration: 1 * time.Millisecond,
	}, nil
}

func BenchmarkCoverageMap(b *testing.B) {
	cm := NewCoverageMap(65536)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		cm.RecordEdge(uint32(i), uint32(i+1))
	}
}

func BenchmarkContentHash(b *testing.B) {
	data := []byte("benchmark test data for hashing")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ContentHash(data)
	}
}
