package state

import (
	"sync"
	"testing"
	"time"
)

func TestNewPool(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	if p == nil {
		t.Fatal("Expected non-nil pool")
	}

	if p.Size() != 0 {
		t.Errorf("Expected size 0, got %d", p.Size())
	}
}

func TestPool_AddAndGet(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	// Add value
	ok := p.Add("token", "abc123")
	if !ok {
		t.Error("Failed to add value")
	}

	// Get value
	value, found := p.Get("token")
	if !found {
		t.Error("Value not found")
	}

	if value != "abc123" {
		t.Errorf("Expected 'abc123', got '%s'", value)
	}

	// Size should be 1
	if p.Size() != 1 {
		t.Errorf("Expected size 1, got %d", p.Size())
	}
}

func TestPool_GetLatest(t *testing.T) {
	config := DefaultPoolConfig()
	config.AllowDuplicates = true
	p := NewPool(config)
	defer p.Close()

	p.Add("token", "first")
	p.Add("token", "second")
	p.Add("token", "third")

	value, found := p.GetLatest("token")
	if !found {
		t.Error("Value not found")
	}

	if value != "third" {
		t.Errorf("Expected 'third', got '%s'", value)
	}
}

func TestPool_GetAll(t *testing.T) {
	config := DefaultPoolConfig()
	config.AllowDuplicates = true
	p := NewPool(config)
	defer p.Close()

	p.Add("items", "a")
	p.Add("items", "b")
	p.Add("items", "c")

	values := p.GetAll("items")
	if len(values) != 3 {
		t.Errorf("Expected 3 values, got %d", len(values))
	}
}

func TestPool_DeduplicationDisabled(t *testing.T) {
	config := DefaultPoolConfig()
	config.AllowDuplicates = false
	p := NewPool(config)
	defer p.Close()

	p.Add("token", "same_value")
	p.Add("token", "same_value")
	p.Add("token", "same_value")

	values := p.GetAll("token")
	if len(values) != 1 {
		t.Errorf("Expected 1 value (deduplicated), got %d", len(values))
	}
}

func TestPool_DeduplicationEnabled(t *testing.T) {
	config := DefaultPoolConfig()
	config.AllowDuplicates = true
	p := NewPool(config)
	defer p.Close()

	p.Add("token", "same_value")
	p.Add("token", "same_value")
	p.Add("token", "same_value")

	values := p.GetAll("token")
	if len(values) != 3 {
		t.Errorf("Expected 3 values (duplicates allowed), got %d", len(values))
	}
}

func TestPool_TTLExpiration(t *testing.T) {
	config := DefaultPoolConfig()
	config.CleanupInterval = 0 // Disable auto cleanup
	p := NewPool(config)
	defer p.Close()

	// Add with very short TTL
	p.AddWithTTL("token", "expires_soon", 50*time.Millisecond)

	// Should be found immediately
	_, found := p.Get("token")
	if !found {
		t.Error("Value should be found immediately")
	}

	// Wait for expiration
	time.Sleep(60 * time.Millisecond)

	// Should not be found after expiration
	_, found = p.Get("token")
	if found {
		t.Error("Value should be expired")
	}
}

func TestPool_Has(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	if p.Has("missing") {
		t.Error("Should not have missing key")
	}

	p.Add("exists", "value")

	if !p.Has("exists") {
		t.Error("Should have existing key")
	}
}

func TestPool_Remove(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	p.Add("key1", "value1")
	p.Add("key2", "value2")

	count := p.Remove("key1")
	if count != 1 {
		t.Errorf("Expected 1 removed, got %d", count)
	}

	if p.Has("key1") {
		t.Error("Key1 should be removed")
	}

	if !p.Has("key2") {
		t.Error("Key2 should still exist")
	}
}

func TestPool_RemoveValue(t *testing.T) {
	config := DefaultPoolConfig()
	config.AllowDuplicates = true
	p := NewPool(config)
	defer p.Close()

	p.Add("items", "a")
	p.Add("items", "b")
	p.Add("items", "c")

	removed := p.RemoveValue("items", "b")
	if !removed {
		t.Error("Should have removed value")
	}

	values := p.GetAll("items")
	if len(values) != 2 {
		t.Errorf("Expected 2 values, got %d", len(values))
	}

	for _, v := range values {
		if v == "b" {
			t.Error("Value 'b' should be removed")
		}
	}
}

func TestPool_Clear(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	p.Add("key1", "value1")
	p.Add("key2", "value2")
	p.Add("key3", "value3")

	if p.Size() != 3 {
		t.Errorf("Expected size 3, got %d", p.Size())
	}

	p.Clear()

	if p.Size() != 0 {
		t.Errorf("Expected size 0 after clear, got %d", p.Size())
	}
}

func TestPool_Keys(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	p.Add("key1", "value1")
	p.Add("key2", "value2")
	p.Add("key3", "value3")

	keys := p.Keys()
	if len(keys) != 3 {
		t.Errorf("Expected 3 keys, got %d", len(keys))
	}
}

func TestPool_MaxEntriesPerKey(t *testing.T) {
	config := DefaultPoolConfig()
	config.MaxEntriesPerKey = 3
	config.AllowDuplicates = true
	p := NewPool(config)
	defer p.Close()

	for i := 0; i < 10; i++ {
		p.Add("key", "value_"+string(rune('0'+i)))
	}

	values := p.GetAll("key")
	if len(values) != 3 {
		t.Errorf("Expected 3 values (max per key), got %d", len(values))
	}
}

func TestPool_MaxTotalEntries(t *testing.T) {
	config := DefaultPoolConfig()
	config.MaxTotalEntries = 5
	config.CleanupInterval = 0
	p := NewPool(config)
	defer p.Close()

	for i := 0; i < 10; i++ {
		p.Add("key_"+string(rune('0'+i)), "value")
	}

	if p.Size() > 5 {
		t.Errorf("Expected max 5 entries, got %d", p.Size())
	}
}

func TestPool_Cleanup(t *testing.T) {
	config := DefaultPoolConfig()
	config.CleanupInterval = 0
	p := NewPool(config)
	defer p.Close()

	// Add some entries with short TTL
	p.AddWithTTL("expired1", "value", 10*time.Millisecond)
	p.AddWithTTL("expired2", "value", 10*time.Millisecond)
	p.Add("valid", "value")

	time.Sleep(20 * time.Millisecond)

	removed := p.Cleanup()
	if removed != 2 {
		t.Errorf("Expected 2 removed, got %d", removed)
	}

	if p.Size() != 1 {
		t.Errorf("Expected 1 remaining, got %d", p.Size())
	}
}

func TestPool_Snapshot(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	p.Add("key1", "value1")
	p.Add("key2", "value2")

	snapshot := p.Snapshot()

	if len(snapshot) != 2 {
		t.Errorf("Expected 2 keys in snapshot, got %d", len(snapshot))
	}

	if snapshot["key1"][0] != "value1" {
		t.Errorf("Expected value1, got %s", snapshot["key1"][0])
	}
}

func TestPool_Import(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	data := map[string][]string{
		"tokens": {"abc", "def", "ghi"},
		"ids":    {"123", "456"},
	}

	count := p.Import(data)
	if count != 5 {
		t.Errorf("Expected 5 imported, got %d", count)
	}

	if p.Size() != 5 {
		t.Errorf("Expected size 5, got %d", p.Size())
	}

	tokens := p.GetAll("tokens")
	if len(tokens) != 3 {
		t.Errorf("Expected 3 tokens, got %d", len(tokens))
	}
}

func TestPool_Stats(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	p.Add("key1", "value1")
	p.Add("key2", "value2")
	p.Get("key1")
	p.Get("key1")

	stats := p.Stats()

	if stats.TotalEntries != 2 {
		t.Errorf("Expected 2 total entries, got %d", stats.TotalEntries)
	}

	if stats.KeyCount != 2 {
		t.Errorf("Expected 2 keys, got %d", stats.KeyCount)
	}

	if stats.AddedCount != 2 {
		t.Errorf("Expected 2 added, got %d", stats.AddedCount)
	}

	if stats.RetrievedCount != 2 {
		t.Errorf("Expected 2 retrieved, got %d", stats.RetrievedCount)
	}
}

func TestPoolValueSource(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	p.Add("token", "secret_value")

	source := NewPoolValueSource(p)
	value, found := source.GetValue("token")

	if !found {
		t.Error("Value should be found via ValueSource")
	}

	if value != "secret_value" {
		t.Errorf("Expected 'secret_value', got '%s'", value)
	}
}

func TestPool_ConcurrentAccess(t *testing.T) {
	p := NewPool(nil)
	defer p.Close()

	var wg sync.WaitGroup
	numGoroutines := 100
	numOperations := 100

	// Concurrent writes
	wg.Add(numGoroutines)
	for i := 0; i < numGoroutines; i++ {
		go func(id int) {
			defer wg.Done()
			for j := 0; j < numOperations; j++ {
				key := "key_" + string(rune('0'+id%10))
				p.Add(key, "value")
			}
		}(i)
	}

	// Concurrent reads
	wg.Add(numGoroutines)
	for i := 0; i < numGoroutines; i++ {
		go func(id int) {
			defer wg.Done()
			for j := 0; j < numOperations; j++ {
				key := "key_" + string(rune('0'+id%10))
				p.Get(key)
			}
		}(i)
	}

	wg.Wait()

	// Should complete without race conditions
	if p.Size() == 0 {
		t.Log("Pool operations completed successfully")
	}
}

func BenchmarkPool_Add(b *testing.B) {
	p := NewPool(nil)
	defer p.Close()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		p.Add("key", "value")
	}
}

func BenchmarkPool_Get(b *testing.B) {
	p := NewPool(nil)
	defer p.Close()
	p.Add("key", "value")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		p.Get("key")
	}
}

func BenchmarkPool_ConcurrentAddGet(b *testing.B) {
	p := NewPool(nil)
	defer p.Close()

	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			if i%2 == 0 {
				p.Add("key", "value")
			} else {
				p.Get("key")
			}
			i++
		}
	})
}
