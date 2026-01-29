package mutator

import (
	"bytes"
	"testing"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
)

// MockMutator is a test mutator implementation
type MockMutator struct {
	name       string
	mutateFunc func([]byte) ([]byte, error)
}

func NewMockMutator(name string, fn func([]byte) ([]byte, error)) *MockMutator {
	return &MockMutator{
		name:       name,
		mutateFunc: fn,
	}
}

func (m *MockMutator) Name() string {
	return m.name
}

func (m *MockMutator) Description() string {
	return "Mock mutator for testing"
}

func (m *MockMutator) Mutate(input []byte) ([]byte, error) {
	if m.mutateFunc != nil {
		return m.mutateFunc(input)
	}
	return append(input, '_', 'm', 'u', 't', 'a', 't', 'e', 'd'), nil
}

func (m *MockMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

func (m *MockMutator) Type() types.MutationType {
	return types.BitFlip
}

// --- Registry Tests ---

func TestRegistry_Register(t *testing.T) {
	reg := NewRegistry()

	m1 := NewMockMutator("mutator1", nil)
	m2 := NewMockMutator("mutator2", nil)

	reg.Register(m1)
	reg.Register(m2)

	if reg.Count() != 2 {
		t.Errorf("expected count 2, got %d", reg.Count())
	}

	names := reg.Names()
	if len(names) != 2 {
		t.Errorf("expected 2 names, got %d", len(names))
	}
	if names[0] != "mutator1" || names[1] != "mutator2" {
		t.Errorf("unexpected names: %v", names)
	}
}

func TestRegistry_Get(t *testing.T) {
	reg := NewRegistry()

	m := NewMockMutator("testmutator", nil)
	reg.Register(m)

	found, exists := reg.Get("testmutator")
	if !exists {
		t.Error("expected mutator to exist")
	}
	if found.Name() != "testmutator" {
		t.Errorf("expected name 'testmutator', got '%s'", found.Name())
	}

	_, exists = reg.Get("nonexistent")
	if exists {
		t.Error("expected nonexistent mutator to not exist")
	}
}

func TestRegistry_GetByType(t *testing.T) {
	reg := NewRegistry()

	m1 := NewMockMutator("m1", nil)
	m2 := NewMockMutator("m2", nil)
	reg.Register(m1)
	reg.Register(m2)

	mutators := reg.GetByType(types.BitFlip)
	if len(mutators) != 2 {
		t.Errorf("expected 2 mutators, got %d", len(mutators))
	}
}

func TestRegistry_All(t *testing.T) {
	reg := NewRegistry()

	for i := 0; i < 5; i++ {
		reg.Register(NewMockMutator("m"+string(rune('0'+i)), nil))
	}

	all := reg.All()
	if len(all) != 5 {
		t.Errorf("expected 5 mutators, got %d", len(all))
	}
}

func TestRegistry_Remove(t *testing.T) {
	reg := NewRegistry()

	m := NewMockMutator("removeme", nil)
	reg.Register(m)

	if reg.Count() != 1 {
		t.Errorf("expected count 1, got %d", reg.Count())
	}

	removed := reg.Remove("removeme")
	if !removed {
		t.Error("expected removal to succeed")
	}

	if reg.Count() != 0 {
		t.Errorf("expected count 0, got %d", reg.Count())
	}

	// Try removing again
	removed = reg.Remove("removeme")
	if removed {
		t.Error("expected second removal to fail")
	}
}

// --- RandomSelector Tests ---

func TestRandomSelector_SelectMutator(t *testing.T) {
	selector := NewRandomSelector()

	// Test with empty slice
	m := selector.SelectMutator(nil)
	if m != nil {
		t.Error("expected nil for empty slice")
	}

	// Test with single mutator
	mutators := []Mutator{NewMockMutator("single", nil)}
	m = selector.SelectMutator(mutators)
	if m == nil || m.Name() != "single" {
		t.Error("expected 'single' mutator")
	}

	// Test with multiple mutators (just verify it returns something)
	mutators = []Mutator{
		NewMockMutator("m1", nil),
		NewMockMutator("m2", nil),
		NewMockMutator("m3", nil),
	}

	counts := make(map[string]int)
	for i := 0; i < 100; i++ {
		m = selector.SelectMutator(mutators)
		if m != nil {
			counts[m.Name()]++
		}
	}

	// Each mutator should be selected at least once (probabilistic)
	if len(counts) < 2 {
		t.Log("Warning: random selection may not be very random in small samples")
	}
}

func TestRandomSelector_ShouldMutate(t *testing.T) {
	selector := NewRandomSelector()

	// Probability 0 - should never mutate
	for i := 0; i < 10; i++ {
		if selector.ShouldMutate(0) {
			t.Error("should not mutate with probability 0")
		}
	}

	// Probability 1 - should always mutate
	for i := 0; i < 10; i++ {
		if !selector.ShouldMutate(1.0) {
			t.Error("should always mutate with probability 1.0")
		}
	}

	// Probability 0.5 - should mutate roughly half the time
	mutateCount := 0
	for i := 0; i < 1000; i++ {
		if selector.ShouldMutate(0.5) {
			mutateCount++
		}
	}
	// Accept wide range due to randomness
	if mutateCount < 300 || mutateCount > 700 {
		t.Errorf("expected ~500 mutations, got %d", mutateCount)
	}
}

// --- WeightedSelector Tests ---

func TestWeightedSelector_SelectMutator(t *testing.T) {
	selector := NewWeightedSelector()

	// Test with empty slice
	m := selector.SelectMutator(nil)
	if m != nil {
		t.Error("expected nil for empty slice")
	}

	// Set up weighted selection
	selector.SetWeight("heavy", 100)
	selector.SetWeight("light", 1)

	mutators := []Mutator{
		NewMockMutator("heavy", nil),
		NewMockMutator("light", nil),
	}

	counts := make(map[string]int)
	for i := 0; i < 100; i++ {
		m = selector.SelectMutator(mutators)
		if m != nil {
			counts[m.Name()]++
		}
	}

	// Heavy should be selected much more often
	if counts["heavy"] < counts["light"]*2 {
		t.Errorf("expected heavy to be selected more often: heavy=%d, light=%d",
			counts["heavy"], counts["light"])
	}
}

func TestWeightedSelector_Reset(t *testing.T) {
	selector := NewWeightedSelector()
	selector.SetWeight("test", 10)
	selector.Reset()

	// After reset, weights should be cleared
	// This is somewhat internal behavior, but we can verify through selection behavior
	mutators := []Mutator{
		NewMockMutator("m1", nil),
		NewMockMutator("m2", nil),
	}

	counts := make(map[string]int)
	for i := 0; i < 100; i++ {
		m := selector.SelectMutator(mutators)
		if m != nil {
			counts[m.Name()]++
		}
	}

	// Should be roughly equal distribution after reset
	if len(counts) != 2 {
		t.Log("Both mutators should be selected after reset")
	}
}

// --- InputType Tests ---

func TestInputType_String(t *testing.T) {
	tests := []struct {
		inputType InputType
		expected  string
	}{
		{TypeUnknown, "unknown"},
		{TypeString, "string"},
		{TypeInteger, "integer"},
		{TypeFloat, "float"},
		{TypeJSON, "json"},
		{TypeXML, "xml"},
		{TypeHTML, "html"},
		{TypeURL, "url"},
		{TypeEmail, "email"},
		{TypeUUID, "uuid"},
		{TypeJWT, "jwt"},
		{TypeBase64, "base64"},
		{TypeHex, "hex"},
	}

	for _, tt := range tests {
		if tt.inputType.String() != tt.expected {
			t.Errorf("expected %s, got %s", tt.expected, tt.inputType.String())
		}
	}
}

// --- MutatorEngine Tests ---

func TestMutatorEngine_New(t *testing.T) {
	engine := NewMutatorEngine()

	if engine == nil {
		t.Fatal("engine should not be nil")
	}

	if engine.Registry() == nil {
		t.Error("registry should not be nil")
	}
}

func TestMutatorEngine_WithConfig(t *testing.T) {
	config := &MutatorEngineConfig{
		Probability:  0.8,
		MaxMutations: 3,
		Strategy:     NewWeightedSelector(),
	}

	engine := NewMutatorEngineWithConfig(config)

	if engine == nil {
		t.Fatal("engine should not be nil")
	}
}

func TestMutatorEngine_Register(t *testing.T) {
	engine := NewMutatorEngine()

	m := NewMockMutator("test", nil)
	engine.Register(m)

	if engine.Registry().Count() != 1 {
		t.Errorf("expected 1 mutator, got %d", engine.Registry().Count())
	}
}

func TestMutatorEngine_DetectType(t *testing.T) {
	engine := NewMutatorEngine()

	tests := []struct {
		input    []byte
		expected InputType
	}{
		{[]byte(`{"key": "value"}`), TypeJSON},
		{[]byte(`[1, 2, 3]`), TypeJSON},
		{[]byte(`<xml>data</xml>`), TypeXML},
		{[]byte(`12345`), TypeInteger},
		{[]byte(`-123`), TypeInteger},
		{[]byte(`550e8400-e29b-41d4-a716-446655440000`), TypeUUID},
		{[]byte(`hello world`), TypeUnknown}, // Falls through to unknown
	}

	for _, tt := range tests {
		detected := engine.DetectType(tt.input)
		if detected != tt.expected {
			t.Errorf("input %q: expected %s, got %s",
				tt.input, tt.expected.String(), detected.String())
		}
	}
}

func TestMutatorEngine_Mutate(t *testing.T) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)

	m := NewMockMutator("appender", func(input []byte) ([]byte, error) {
		return append(input, []byte("_MUTATED")...), nil
	})
	engine.Register(m)

	input := []byte("original")
	result := engine.Mutate(input)

	if !result.Success {
		t.Errorf("mutation should succeed: %v", result.Error)
	}

	if !bytes.Contains(result.Mutated, []byte("_MUTATED")) {
		t.Errorf("expected mutated output, got: %s", result.Mutated)
	}

	if !bytes.Equal(result.Original, input) {
		t.Error("original should be preserved")
	}
}

func TestMutatorEngine_MutateNoMutators(t *testing.T) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)

	input := []byte("original")
	result := engine.Mutate(input)

	if !result.Success {
		t.Error("should succeed even with no mutators")
	}

	if !bytes.Equal(result.Mutated, input) {
		t.Error("should return original when no mutators")
	}
}

func TestMutatorEngine_MutateZeroProbability(t *testing.T) {
	engine := NewMutatorEngine()
	engine.SetProbability(0)

	m := NewMockMutator("test", func(input []byte) ([]byte, error) {
		return append(input, []byte("_MUTATED")...), nil
	})
	engine.Register(m)

	input := []byte("original")
	result := engine.Mutate(input)

	if !result.Success {
		t.Error("should succeed")
	}

	// With probability 0, should not mutate
	if !bytes.Equal(result.Mutated, input) {
		t.Error("should not mutate with probability 0")
	}
}

func TestMutatorEngine_MutateN(t *testing.T) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)

	counter := 0
	m := NewMockMutator("counter", func(input []byte) ([]byte, error) {
		counter++
		return append(input, 'X'), nil
	})
	engine.Register(m)

	input := []byte("start")
	result := engine.MutateN(input, 5)

	if !result.Success {
		t.Errorf("should succeed: %v", result.Error)
	}

	// Should have 5 'X' appended
	expectedLen := len(input) + 5
	if len(result.Mutated) != expectedLen {
		t.Errorf("expected length %d, got %d", expectedLen, len(result.Mutated))
	}
}

func TestMutatorEngine_MutateChain(t *testing.T) {
	engine := NewMutatorEngineWithConfig(&MutatorEngineConfig{
		Probability:  1.0,
		MaxMutations: 3,
		Strategy:     NewRandomSelector(),
	})

	m := NewMockMutator("test", func(input []byte) ([]byte, error) {
		return append(input, 'X'), nil
	})
	engine.Register(m)

	input := []byte("start")
	result := engine.MutateChain(input)

	if !result.Success {
		t.Errorf("should succeed: %v", result.Error)
	}

	// Should have 1-3 'X' appended
	appendedCount := len(result.Mutated) - len(input)
	if appendedCount < 1 || appendedCount > 3 {
		t.Errorf("expected 1-3 appended, got %d", appendedCount)
	}
}

func TestMutatorEngine_SetProbability(t *testing.T) {
	engine := NewMutatorEngine()

	// Test clamping
	engine.SetProbability(-0.5)
	// No panic expected

	engine.SetProbability(1.5)
	// No panic expected

	engine.SetProbability(0.5)
	// Normal case
}

// --- Helper Function Tests ---

func TestSecureRandomInt(t *testing.T) {
	// Test with 0
	result := secureRandomInt(0)
	if result != 0 {
		t.Errorf("expected 0 for max=0, got %d", result)
	}

	// Test distribution
	const max = 10
	counts := make(map[int]int)
	for i := 0; i < 1000; i++ {
		n := secureRandomInt(max)
		if n < 0 || n >= max {
			t.Errorf("random number %d out of range [0, %d)", n, max)
		}
		counts[n]++
	}

	// Each number should appear at least once
	if len(counts) != max {
		t.Log("Warning: not all values appeared in random sample")
	}
}

func TestSecureRandomBytes(t *testing.T) {
	b := secureRandomBytes(16)
	if len(b) != 16 {
		t.Errorf("expected 16 bytes, got %d", len(b))
	}

	// Check they're not all zeros
	allZero := true
	for _, v := range b {
		if v != 0 {
			allZero = false
			break
		}
	}
	if allZero {
		t.Error("random bytes should not be all zeros")
	}
}

// --- Benchmark Tests ---

func BenchmarkRegistry_Register(b *testing.B) {
	reg := NewRegistry()
	for i := 0; i < b.N; i++ {
		m := NewMockMutator("m"+string(rune(i)), nil)
		reg.Register(m)
	}
}

func BenchmarkRandomSelector_SelectMutator(b *testing.B) {
	selector := NewRandomSelector()
	mutators := make([]Mutator, 10)
	for i := range mutators {
		mutators[i] = NewMockMutator("m"+string(rune(i)), nil)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		selector.SelectMutator(mutators)
	}
}

func BenchmarkMutatorEngine_Mutate(b *testing.B) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)
	engine.Register(NewMockMutator("test", func(input []byte) ([]byte, error) {
		return append(input, 'X'), nil
	}))

	input := []byte("test input data for mutation")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.Mutate(input)
	}
}

func BenchmarkMutatorEngine_DetectType(b *testing.B) {
	engine := NewMutatorEngine()
	inputs := [][]byte{
		[]byte(`{"key": "value"}`),
		[]byte(`<xml>data</xml>`),
		[]byte(`12345`),
		[]byte(`hello world`),
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.DetectType(inputs[i%len(inputs)])
	}
}
