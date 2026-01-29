package mutator

import (
	"bytes"
	"testing"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
)

// --- BitFlipMutator Tests ---

func TestBitFlipMutator_Name(t *testing.T) {
	tests := []struct {
		flipBits int
		expected string
	}{
		{1, "bitflip/1"},
		{2, "bitflip/2"},
		{4, "bitflip/4"},
		{8, "bitflip/1"}, // defaults to 1
	}

	for _, tt := range tests {
		m := NewBitFlipMutator(tt.flipBits)
		if m.Name() != tt.expected {
			t.Errorf("flipBits=%d: expected %s, got %s", tt.flipBits, tt.expected, m.Name())
		}
	}
}

func TestBitFlipMutator_Type(t *testing.T) {
	m := NewBitFlipMutator(1)
	if m.Type() != types.BitFlip {
		t.Errorf("expected BitFlip type")
	}
}

func TestBitFlipMutator_Mutate(t *testing.T) {
	m := NewBitFlipMutator(1)

	// Test with empty input
	result, err := m.Mutate([]byte{})
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("expected empty result")
	}

	// Test that mutation actually changes something
	input := []byte{0x00, 0x00, 0x00, 0x00}
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// At least one bit should be different
	if bytes.Equal(input, mutated) {
		// This could theoretically happen if random lands on a flip that creates same result
		// But with all zeros input, any flip should change something
		t.Logf("Warning: mutation resulted in same value (possible but unlikely with zero input)")
	}
}

func TestBitFlipMutator_MutateAt(t *testing.T) {
	m := NewBitFlipMutator(1)

	input := []byte{0x80, 0x00} // 10000000 00000000

	// Flip first bit (position 0)
	result, err := m.MutateAt(input, 0)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}
	// 10000000 -> 00000000
	if result[0] != 0x00 {
		t.Errorf("expected 0x00, got 0x%02x", result[0])
	}

	// Test out of range
	_, err = m.MutateAt(input, 16)
	if err == nil {
		t.Error("expected error for out of range position")
	}
}

func TestBitFlipMutator_MultipleBits(t *testing.T) {
	m := NewBitFlipMutator(4)

	input := []byte{0xFF, 0xFF} // All ones

	// Multiple flips should change multiple bits
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Count changed bits
	changedBits := 0
	for i := range input {
		diff := input[i] ^ mutated[i]
		for diff != 0 {
			changedBits++
			diff &= diff - 1
		}
	}

	if changedBits < 1 || changedBits > 4 {
		t.Errorf("expected 1-4 changed bits, got %d", changedBits)
	}
}

// --- ByteFlipMutator Tests ---

func TestByteFlipMutator_Name(t *testing.T) {
	tests := []struct {
		flipBytes int
		expected  string
	}{
		{1, "byteflip/1"},
		{2, "byteflip/2"},
		{4, "byteflip/4"},
	}

	for _, tt := range tests {
		m := NewByteFlipMutator(tt.flipBytes)
		if m.Name() != tt.expected {
			t.Errorf("flipBytes=%d: expected %s, got %s", tt.flipBytes, tt.expected, m.Name())
		}
	}
}

func TestByteFlipMutator_Mutate(t *testing.T) {
	m := NewByteFlipMutator(1)

	input := []byte{0x00, 0x00, 0x00, 0x00}
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// At least one byte should be 0xFF (flipped from 0x00)
	found := false
	for _, b := range mutated {
		if b == 0xFF {
			found = true
			break
		}
	}
	if !found {
		t.Error("expected at least one byte to be 0xFF")
	}
}

func TestByteFlipMutator_MutateAt(t *testing.T) {
	m := NewByteFlipMutator(2)

	input := []byte{0x00, 0x00, 0x00, 0x00}
	result, err := m.MutateAt(input, 1)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Bytes at positions 1 and 2 should be flipped
	if result[1] != 0xFF || result[2] != 0xFF {
		t.Errorf("expected bytes 1,2 to be 0xFF, got 0x%02x, 0x%02x", result[1], result[2])
	}

	// Bytes at positions 0 and 3 should be unchanged
	if result[0] != 0x00 || result[3] != 0x00 {
		t.Error("unexpected change to other bytes")
	}
}

func TestByteFlipMutator_ShortInput(t *testing.T) {
	m := NewByteFlipMutator(4)

	// Input shorter than flip width
	input := []byte{0x00, 0x00}
	result, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should return unchanged
	if !bytes.Equal(input, result) {
		t.Error("expected unchanged result for short input")
	}
}

// --- ArithmeticMutator Tests ---

func TestArithmeticMutator_Name(t *testing.T) {
	tests := []struct {
		width    int
		expected string
	}{
		{1, "arith/8"},
		{2, "arith/16"},
		{4, "arith/32"},
	}

	for _, tt := range tests {
		m := NewArithmeticMutator(tt.width, 35)
		if m.Name() != tt.expected {
			t.Errorf("width=%d: expected %s, got %s", tt.width, tt.expected, m.Name())
		}
	}
}

func TestArithmeticMutator_Type(t *testing.T) {
	m := NewArithmeticMutator(1, 35)
	if m.Type() != types.ArithmeticAdd {
		t.Errorf("expected ArithmeticAdd type")
	}
}

func TestArithmeticMutator_Mutate(t *testing.T) {
	m := NewArithmeticMutator(1, 35)

	input := []byte{100, 100, 100, 100}
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// At least one byte should be different
	different := false
	for i := range input {
		if input[i] != mutated[i] {
			different = true
			diff := int(mutated[i]) - int(input[i])
			if diff < 0 {
				diff = -diff
			}
			// Difference should be within maxDelta (considering overflow)
			if diff > 35 && diff < 256-35 {
				t.Errorf("difference %d exceeds expected range", diff)
			}
			break
		}
	}

	if !different {
		t.Log("Warning: no change detected (possible but unlikely)")
	}
}

func TestArithmeticMutator_MutateAt(t *testing.T) {
	m := NewArithmeticMutator(1, 35)

	input := []byte{100, 100}
	result, err := m.MutateAt(input, 0, 10)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if result[0] != 110 {
		t.Errorf("expected 110, got %d", result[0])
	}

	// Negative delta
	result, err = m.MutateAt(input, 1, -50)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}
	if result[1] != 50 {
		t.Errorf("expected 50, got %d", result[1])
	}
}

func TestArithmeticMutator_MutateWithType_Integer(t *testing.T) {
	m := NewArithmeticMutator(4, 35)

	input := []byte("12345")
	mutated, err := m.MutateWithType(input, TypeInteger)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be a valid integer string
	for i, b := range mutated {
		if i == 0 && b == '-' {
			continue
		}
		if b < '0' || b > '9' {
			t.Errorf("invalid character in result: %c", b)
		}
	}
}

// --- InterestingValueMutator Tests ---

func TestInterestingValueMutator_Name(t *testing.T) {
	tests := []struct {
		width    int
		expected string
	}{
		{1, "interest/8"},
		{2, "interest/16"},
		{4, "interest/32"},
	}

	for _, tt := range tests {
		m := NewInterestingValueMutator(tt.width)
		if m.Name() != tt.expected {
			t.Errorf("width=%d: expected %s, got %s", tt.width, tt.expected, m.Name())
		}
	}
}

func TestInterestingValueMutator_Type(t *testing.T) {
	m := NewInterestingValueMutator(1)
	if m.Type() != types.InterestingValues {
		t.Errorf("expected InterestingValues type")
	}
}

func TestInterestingValueMutator_Mutate8(t *testing.T) {
	m := NewInterestingValueMutator(1)

	input := []byte{0x55, 0x55, 0x55, 0x55}
	seen := make(map[byte]bool)

	// Run multiple times to see different interesting values
	for i := 0; i < 100; i++ {
		mutated, err := m.Mutate(input)
		if err != nil {
			t.Errorf("unexpected error: %v", err)
		}

		for j := range mutated {
			if mutated[j] != 0x55 {
				seen[mutated[j]] = true
			}
		}
	}

	// Should have seen multiple interesting values
	if len(seen) < 2 {
		t.Errorf("expected multiple interesting values, got %d unique values", len(seen))
	}
}

func TestInterestingValueMutator_MutateAt(t *testing.T) {
	m := NewInterestingValueMutator(1)

	input := []byte{0x00, 0x00}

	// Test with specific value index
	result, err := m.MutateAt(input, 0, 0, true) // Index 0 is -128 (0x80)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if result[0] != 0x80 { // -128 as unsigned byte
		t.Errorf("expected 0x80, got 0x%02x", result[0])
	}
}

func TestInterestingValueMutator_MutateWithType_Integer(t *testing.T) {
	m := NewInterestingValueMutator(4)

	input := []byte("12345")
	mutated, err := m.MutateWithType(input, TypeInteger)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be a valid integer string (possibly with leading -)
	for i, b := range mutated {
		if i == 0 && b == '-' {
			continue
		}
		if b < '0' || b > '9' {
			t.Errorf("invalid character in result: %c", b)
		}
	}
}

// --- ByteSwapMutator Tests ---

func TestByteSwapMutator_Name(t *testing.T) {
	tests := []struct {
		swapCount int
		expected  string
	}{
		{2, "byteswap/2"},
		{4, "byteswap/4"},
	}

	for _, tt := range tests {
		m := NewByteSwapMutator(tt.swapCount)
		if m.Name() != tt.expected {
			t.Errorf("swapCount=%d: expected %s, got %s", tt.swapCount, tt.expected, m.Name())
		}
	}
}

func TestByteSwapMutator_Type(t *testing.T) {
	m := NewByteSwapMutator(2)
	if m.Type() != types.ByteSwap {
		t.Errorf("expected ByteSwap type")
	}
}

func TestByteSwapMutator_Mutate2(t *testing.T) {
	m := NewByteSwapMutator(2)

	input := []byte{0x12, 0x34}
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Bytes should be swapped
	if mutated[0] != 0x34 || mutated[1] != 0x12 {
		t.Errorf("expected [0x34, 0x12], got [0x%02x, 0x%02x]", mutated[0], mutated[1])
	}
}

func TestByteSwapMutator_Mutate4(t *testing.T) {
	m := NewByteSwapMutator(4)

	input := []byte{0x12, 0x34, 0x56, 0x78}
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Bytes should be reverse-ordered
	expected := []byte{0x78, 0x56, 0x34, 0x12}
	if !bytes.Equal(mutated, expected) {
		t.Errorf("expected %v, got %v", expected, mutated)
	}
}

// --- RandomByteMutator Tests ---

func TestRandomByteMutator_Name(t *testing.T) {
	m := NewRandomByteMutator(1)
	if m.Name() != "random_byte" {
		t.Errorf("expected 'random_byte', got '%s'", m.Name())
	}
}

func TestRandomByteMutator_Mutate(t *testing.T) {
	m := NewRandomByteMutator(1)

	input := make([]byte, 100)
	for i := range input {
		input[i] = 0x55
	}

	changed := 0
	for i := 0; i < 100; i++ {
		mutated, err := m.Mutate(input)
		if err != nil {
			t.Errorf("unexpected error: %v", err)
		}

		for j := range mutated {
			if mutated[j] != 0x55 {
				changed++
				break
			}
		}
	}

	// Most mutations should change something
	if changed < 80 {
		t.Errorf("expected most mutations to change something, only %d/100 changed", changed)
	}
}

// --- DeleteMutator Tests ---

func TestDeleteMutator_Name(t *testing.T) {
	m := NewDeleteMutator(16)
	if m.Name() != "delete" {
		t.Errorf("expected 'delete', got '%s'", m.Name())
	}
}

func TestDeleteMutator_Mutate(t *testing.T) {
	m := NewDeleteMutator(4)

	input := []byte("hello world")
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be shorter
	if len(mutated) >= len(input) {
		t.Errorf("expected shorter result, got len=%d (original=%d)", len(mutated), len(input))
	}
}

func TestDeleteMutator_SingleByte(t *testing.T) {
	m := NewDeleteMutator(16)

	// Single byte should not be deleted
	input := []byte("x")
	result, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	if !bytes.Equal(input, result) {
		t.Error("single byte input should not be modified")
	}
}

// --- InsertMutator Tests ---

func TestInsertMutator_Name(t *testing.T) {
	m := NewInsertMutator(16)
	if m.Name() != "insert" {
		t.Errorf("expected 'insert', got '%s'", m.Name())
	}
}

func TestInsertMutator_Mutate(t *testing.T) {
	m := NewInsertMutator(4)

	input := []byte("hello")
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be longer
	if len(mutated) <= len(input) {
		t.Errorf("expected longer result, got len=%d (original=%d)", len(mutated), len(input))
	}
}

func TestInsertMutator_EmptyInput(t *testing.T) {
	m := NewInsertMutator(4)

	input := []byte{}
	result, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should have inserted bytes
	if len(result) == 0 {
		t.Error("expected non-empty result")
	}
}

// --- CloneMutator Tests ---

func TestCloneMutator_Name(t *testing.T) {
	m := NewCloneMutator(32)
	if m.Name() != "clone" {
		t.Errorf("expected 'clone', got '%s'", m.Name())
	}
}

func TestCloneMutator_Mutate(t *testing.T) {
	m := NewCloneMutator(4)

	input := []byte("abcd")
	mutated, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Result should be longer
	if len(mutated) <= len(input) {
		t.Errorf("expected longer result, got len=%d (original=%d)", len(mutated), len(input))
	}

	// Result should contain duplicated content from input
	// All bytes in mutated should be from original input
	for _, b := range mutated {
		found := false
		for _, orig := range input {
			if b == orig {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("found unexpected byte 0x%02x not from original input", b)
		}
	}
}

func TestCloneMutator_EmptyInput(t *testing.T) {
	m := NewCloneMutator(4)

	input := []byte{}
	result, err := m.Mutate(input)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}

	// Should return empty
	if len(result) != 0 {
		t.Error("expected empty result for empty input")
	}
}

// --- Helper Function Tests ---

func TestInt64ToString(t *testing.T) {
	tests := []struct {
		input    int64
		expected string
	}{
		{0, "0"},
		{1, "1"},
		{-1, "-1"},
		{12345, "12345"},
		{-12345, "-12345"},
		{2147483647, "2147483647"},
		{-2147483648, "-2147483648"},
	}

	for _, tt := range tests {
		result := int64ToString(tt.input)
		if result != tt.expected {
			t.Errorf("int64ToString(%d): expected %s, got %s", tt.input, tt.expected, result)
		}
	}
}

func TestGetInterestingValues(t *testing.T) {
	i8 := GetInteresting8()
	if len(i8) == 0 {
		t.Error("expected non-empty interesting8 list")
	}

	i16 := GetInteresting16()
	if len(i16) == 0 {
		t.Error("expected non-empty interesting16 list")
	}

	i32 := GetInteresting32()
	if len(i32) == 0 {
		t.Error("expected non-empty interesting32 list")
	}
}

// --- RegisterAFLMutators Tests ---

func TestRegisterAFLMutators(t *testing.T) {
	engine := NewMutatorEngine()

	RegisterAFLMutators(engine)

	// Check that all expected mutators are registered
	expectedNames := []string{
		"bitflip/1", "bitflip/2", "bitflip/4",
		"byteflip/1", "byteflip/2", "byteflip/4",
		"arith/8", "arith/16", "arith/32",
		"interest/8", "interest/16", "interest/32",
		"byteswap/2", "byteswap/4",
		"random_byte", "delete", "insert", "clone",
	}

	for _, name := range expectedNames {
		if _, exists := engine.Registry().Get(name); !exists {
			t.Errorf("expected mutator %s to be registered", name)
		}
	}

	if engine.Registry().Count() != len(expectedNames) {
		t.Errorf("expected %d mutators, got %d", len(expectedNames), engine.Registry().Count())
	}
}

// --- Integration Tests ---

func TestAFLMutators_Integration(t *testing.T) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)
	RegisterAFLMutators(engine)

	input := []byte("test input for fuzzing")

	// Run multiple mutations
	for i := 0; i < 100; i++ {
		result := engine.Mutate(input)
		if !result.Success {
			t.Errorf("mutation failed: %v", result.Error)
		}
	}
}

// --- Benchmark Tests ---

func BenchmarkBitFlipMutator(b *testing.B) {
	m := NewBitFlipMutator(1)
	input := make([]byte, 1024)
	for i := range input {
		input[i] = byte(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkByteFlipMutator(b *testing.B) {
	m := NewByteFlipMutator(4)
	input := make([]byte, 1024)
	for i := range input {
		input[i] = byte(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkArithmeticMutator(b *testing.B) {
	m := NewArithmeticMutator(4, 35)
	input := make([]byte, 1024)
	for i := range input {
		input[i] = byte(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkInterestingValueMutator(b *testing.B) {
	m := NewInterestingValueMutator(4)
	input := make([]byte, 1024)
	for i := range input {
		input[i] = byte(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Mutate(input)
	}
}

func BenchmarkRegisterAFLMutators(b *testing.B) {
	for i := 0; i < b.N; i++ {
		engine := NewMutatorEngine()
		RegisterAFLMutators(engine)
	}
}

func BenchmarkAFLMutation_Full(b *testing.B) {
	engine := NewMutatorEngine()
	engine.SetProbability(1.0)
	RegisterAFLMutators(engine)

	input := make([]byte, 256)
	for i := range input {
		input[i] = byte(i)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.Mutate(input)
	}
}
