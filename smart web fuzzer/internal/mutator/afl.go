// Package mutator provides AFL-style mutation strategies.
// AFL (American Fuzzy Lop) is a coverage-guided fuzzer that uses various
// mutation techniques to generate test cases.
package mutator

import (
	"encoding/binary"
	"errors"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
)

// AFL-inspired interesting values for fuzzing
var (
	// Interesting 8-bit values
	interesting8 = []int8{
		-128, // INT8_MIN
		-1,   // 0xFF
		0,    // Zero
		1,    // One
		16,   // Common boundary
		32,   // Space, common boundary
		64,   // Common boundary
		100,  // Common test value
		127,  // INT8_MAX
	}

	// Interesting 16-bit values
	interesting16 = []int16{
		-32768, // INT16_MIN
		-129,   // Just below INT8_MIN
		128,    // Just above INT8_MAX
		255,    // UINT8_MAX
		256,    // UINT8_MAX + 1
		512,    // Common boundary
		1000,   // Common test value
		1024,   // Common boundary (2^10)
		4096,   // Common boundary (2^12)
		32767,  // INT16_MAX
	}

	// Interesting 32-bit values
	interesting32 = []int32{
		-2147483648, // INT32_MIN
		-100663046,  // Large negative
		-32769,      // Just below INT16_MIN
		32768,       // Just above INT16_MAX
		65535,       // UINT16_MAX
		65536,       // UINT16_MAX + 1
		100663045,   // Large positive
		2147483647,  // INT32_MAX
	}
)

// --- BitFlipMutator ---

// BitFlipMutator implements bit-level mutations
type BitFlipMutator struct {
	flipBits int // Number of consecutive bits to flip (1, 2, or 4)
}

// NewBitFlipMutator creates a new BitFlipMutator
// flipBits specifies how many consecutive bits to flip (1, 2, or 4)
func NewBitFlipMutator(flipBits int) *BitFlipMutator {
	if flipBits != 1 && flipBits != 2 && flipBits != 4 {
		flipBits = 1 // default to single bit flip
	}
	return &BitFlipMutator{flipBits: flipBits}
}

// Name returns the mutator name
func (m *BitFlipMutator) Name() string {
	switch m.flipBits {
	case 1:
		return "bitflip/1"
	case 2:
		return "bitflip/2"
	case 4:
		return "bitflip/4"
	default:
		return "bitflip/1"
	}
}

// Description returns the mutator description
func (m *BitFlipMutator) Description() string {
	return "AFL-style bit flipping mutation"
}

// Type returns the mutation type
func (m *BitFlipMutator) Type() types.MutationType {
	return types.BitFlip
}

// Mutate applies bit flip mutation to the input
func (m *BitFlipMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) == 0 {
		return input, nil
	}

	// Create a copy
	result := make([]byte, len(input))
	copy(result, input)

	// Calculate total number of bits
	totalBits := len(input) * 8

	// Select a random bit position
	pos := secureRandomInt(totalBits - m.flipBits + 1)

	// Flip the bits
	for i := 0; i < m.flipBits; i++ {
		bitPos := pos + i
		byteIdx := bitPos / 8
		bitIdx := bitPos % 8
		result[byteIdx] ^= (1 << (7 - bitIdx))
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *BitFlipMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	// Bit flipping is type-agnostic
	return m.Mutate(input)
}

// MutateAt flips bits at a specific position
func (m *BitFlipMutator) MutateAt(input []byte, bitPosition int) ([]byte, error) {
	if len(input) == 0 {
		return input, nil
	}

	totalBits := len(input) * 8
	if bitPosition < 0 || bitPosition+m.flipBits > totalBits {
		return nil, errors.New("bit position out of range")
	}

	result := make([]byte, len(input))
	copy(result, input)

	for i := 0; i < m.flipBits; i++ {
		bitPos := bitPosition + i
		byteIdx := bitPos / 8
		bitIdx := bitPos % 8
		result[byteIdx] ^= (1 << (7 - bitIdx))
	}

	return result, nil
}

// --- ByteFlipMutator ---

// ByteFlipMutator implements byte-level mutations
type ByteFlipMutator struct {
	flipBytes int // Number of consecutive bytes to flip (1, 2, or 4)
}

// NewByteFlipMutator creates a new ByteFlipMutator
// flipBytes specifies how many consecutive bytes to flip (1, 2, or 4)
func NewByteFlipMutator(flipBytes int) *ByteFlipMutator {
	if flipBytes != 1 && flipBytes != 2 && flipBytes != 4 {
		flipBytes = 1 // default to single byte flip
	}
	return &ByteFlipMutator{flipBytes: flipBytes}
}

// Name returns the mutator name
func (m *ByteFlipMutator) Name() string {
	switch m.flipBytes {
	case 1:
		return "byteflip/1"
	case 2:
		return "byteflip/2"
	case 4:
		return "byteflip/4"
	default:
		return "byteflip/1"
	}
}

// Description returns the mutator description
func (m *ByteFlipMutator) Description() string {
	return "AFL-style byte flipping mutation"
}

// Type returns the mutation type
func (m *ByteFlipMutator) Type() types.MutationType {
	return types.BitFlip
}

// Mutate applies byte flip mutation to the input
func (m *ByteFlipMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) < m.flipBytes {
		return input, nil
	}

	result := make([]byte, len(input))
	copy(result, input)

	// Select a random byte position
	pos := secureRandomInt(len(input) - m.flipBytes + 1)

	// Flip the bytes (XOR with 0xFF)
	for i := 0; i < m.flipBytes; i++ {
		result[pos+i] ^= 0xFF
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *ByteFlipMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// MutateAt flips bytes at a specific position
func (m *ByteFlipMutator) MutateAt(input []byte, bytePosition int) ([]byte, error) {
	if len(input) < m.flipBytes {
		return input, nil
	}

	if bytePosition < 0 || bytePosition+m.flipBytes > len(input) {
		return nil, errors.New("byte position out of range")
	}

	result := make([]byte, len(input))
	copy(result, input)

	for i := 0; i < m.flipBytes; i++ {
		result[bytePosition+i] ^= 0xFF
	}

	return result, nil
}

// --- ArithmeticMutator ---

// ArithmeticMutator implements arithmetic mutations
type ArithmeticMutator struct {
	width    int // Byte width: 1, 2, or 4
	maxDelta int // Maximum delta for addition/subtraction
}

// NewArithmeticMutator creates a new ArithmeticMutator
// width specifies the byte width (1, 2, or 4)
// maxDelta specifies the maximum value to add/subtract (default: 35)
func NewArithmeticMutator(width, maxDelta int) *ArithmeticMutator {
	if width != 1 && width != 2 && width != 4 {
		width = 1
	}
	if maxDelta <= 0 {
		maxDelta = 35 // AFL default ARITH_MAX
	}
	return &ArithmeticMutator{
		width:    width,
		maxDelta: maxDelta,
	}
}

// Name returns the mutator name
func (m *ArithmeticMutator) Name() string {
	switch m.width {
	case 1:
		return "arith/8"
	case 2:
		return "arith/16"
	case 4:
		return "arith/32"
	default:
		return "arith/8"
	}
}

// Description returns the mutator description
func (m *ArithmeticMutator) Description() string {
	return "AFL-style arithmetic mutation"
}

// Type returns the mutation type
func (m *ArithmeticMutator) Type() types.MutationType {
	return types.ArithmeticAdd
}

// Mutate applies arithmetic mutation to the input
func (m *ArithmeticMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) < m.width {
		return input, nil
	}

	result := make([]byte, len(input))
	copy(result, input)

	// Select random position
	pos := secureRandomInt(len(input) - m.width + 1)

	// Select random delta (positive or negative)
	delta := secureRandomInt(m.maxDelta*2+1) - m.maxDelta
	if delta == 0 {
		delta = 1
	}

	// Apply arithmetic operation based on width
	switch m.width {
	case 1:
		result[pos] = byte(int(result[pos]) + delta)
	case 2:
		val := binary.BigEndian.Uint16(result[pos:])
		newVal := uint16(int(val) + delta)
		binary.BigEndian.PutUint16(result[pos:], newVal)
	case 4:
		val := binary.BigEndian.Uint32(result[pos:])
		newVal := uint32(int64(val) + int64(delta))
		binary.BigEndian.PutUint32(result[pos:], newVal)
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *ArithmeticMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	// For integers represented as strings, try to mutate the numeric value
	if inputType == TypeInteger && len(input) > 0 {
		return m.mutateIntegerString(input)
	}
	return m.Mutate(input)
}

// mutateIntegerString mutates an integer represented as a string
func (m *ArithmeticMutator) mutateIntegerString(input []byte) ([]byte, error) {
	// Parse the integer
	negative := false
	start := 0
	if input[0] == '-' {
		negative = true
		start = 1
	}

	var val int64
	for i := start; i < len(input); i++ {
		if input[i] < '0' || input[i] > '9' {
			// Not a valid integer, fall back to byte mutation
			return m.Mutate(input)
		}
		val = val*10 + int64(input[i]-'0')
	}

	if negative {
		val = -val
	}

	// Apply delta
	delta := int64(secureRandomInt(m.maxDelta*2+1) - m.maxDelta)
	if delta == 0 {
		delta = 1
	}
	val += delta

	// Convert back to string
	return []byte(int64ToString(val)), nil
}

// MutateAt applies arithmetic operation at a specific position with a specific delta
func (m *ArithmeticMutator) MutateAt(input []byte, pos, delta int) ([]byte, error) {
	if len(input) < m.width {
		return input, nil
	}

	if pos < 0 || pos+m.width > len(input) {
		return nil, errors.New("position out of range")
	}

	result := make([]byte, len(input))
	copy(result, input)

	switch m.width {
	case 1:
		result[pos] = byte(int(result[pos]) + delta)
	case 2:
		val := binary.BigEndian.Uint16(result[pos:])
		newVal := uint16(int(val) + delta)
		binary.BigEndian.PutUint16(result[pos:], newVal)
	case 4:
		val := binary.BigEndian.Uint32(result[pos:])
		newVal := uint32(int64(val) + int64(delta))
		binary.BigEndian.PutUint32(result[pos:], newVal)
	}

	return result, nil
}

// --- InterestingValueMutator ---

// InterestingValueMutator replaces values with "interesting" boundary values
type InterestingValueMutator struct {
	width int // Byte width: 1, 2, or 4
}

// NewInterestingValueMutator creates a new InterestingValueMutator
// width specifies the byte width (1, 2, or 4)
func NewInterestingValueMutator(width int) *InterestingValueMutator {
	if width != 1 && width != 2 && width != 4 {
		width = 1
	}
	return &InterestingValueMutator{width: width}
}

// Name returns the mutator name
func (m *InterestingValueMutator) Name() string {
	switch m.width {
	case 1:
		return "interest/8"
	case 2:
		return "interest/16"
	case 4:
		return "interest/32"
	default:
		return "interest/8"
	}
}

// Description returns the mutator description
func (m *InterestingValueMutator) Description() string {
	return "AFL-style interesting value mutation"
}

// Type returns the mutation type
func (m *InterestingValueMutator) Type() types.MutationType {
	return types.InterestingValues
}

// Mutate applies interesting value mutation to the input
func (m *InterestingValueMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) < m.width {
		return input, nil
	}

	result := make([]byte, len(input))
	copy(result, input)

	// Select random position
	pos := secureRandomInt(len(input) - m.width + 1)

	// Select random interesting value based on width
	switch m.width {
	case 1:
		idx := secureRandomInt(len(interesting8))
		result[pos] = byte(interesting8[idx])
	case 2:
		idx := secureRandomInt(len(interesting16))
		val := interesting16[idx]
		// Randomly choose endianness
		if secureRandomInt(2) == 0 {
			binary.BigEndian.PutUint16(result[pos:], uint16(val))
		} else {
			binary.LittleEndian.PutUint16(result[pos:], uint16(val))
		}
	case 4:
		idx := secureRandomInt(len(interesting32))
		val := interesting32[idx]
		// Randomly choose endianness
		if secureRandomInt(2) == 0 {
			binary.BigEndian.PutUint32(result[pos:], uint32(val))
		} else {
			binary.LittleEndian.PutUint32(result[pos:], uint32(val))
		}
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *InterestingValueMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	// For integers represented as strings, replace with interesting value
	if inputType == TypeInteger {
		return m.mutateIntegerString(input)
	}
	return m.Mutate(input)
}

// mutateIntegerString replaces an integer string with an interesting value
func (m *InterestingValueMutator) mutateIntegerString(input []byte) ([]byte, error) {
	var val int64

	switch m.width {
	case 1:
		idx := secureRandomInt(len(interesting8))
		val = int64(interesting8[idx])
	case 2:
		idx := secureRandomInt(len(interesting16))
		val = int64(interesting16[idx])
	case 4:
		idx := secureRandomInt(len(interesting32))
		val = int64(interesting32[idx])
	}

	return []byte(int64ToString(val)), nil
}

// MutateAt applies interesting value at a specific position with a specific value index
func (m *InterestingValueMutator) MutateAt(input []byte, pos, valueIdx int, bigEndian bool) ([]byte, error) {
	if len(input) < m.width {
		return input, nil
	}

	if pos < 0 || pos+m.width > len(input) {
		return nil, errors.New("position out of range")
	}

	result := make([]byte, len(input))
	copy(result, input)

	switch m.width {
	case 1:
		if valueIdx >= len(interesting8) {
			valueIdx = 0
		}
		result[pos] = byte(interesting8[valueIdx])
	case 2:
		if valueIdx >= len(interesting16) {
			valueIdx = 0
		}
		val := interesting16[valueIdx]
		if bigEndian {
			binary.BigEndian.PutUint16(result[pos:], uint16(val))
		} else {
			binary.LittleEndian.PutUint16(result[pos:], uint16(val))
		}
	case 4:
		if valueIdx >= len(interesting32) {
			valueIdx = 0
		}
		val := interesting32[valueIdx]
		if bigEndian {
			binary.BigEndian.PutUint32(result[pos:], uint32(val))
		} else {
			binary.LittleEndian.PutUint32(result[pos:], uint32(val))
		}
	}

	return result, nil
}

// --- ByteSwapMutator ---

// ByteSwapMutator swaps adjacent bytes
type ByteSwapMutator struct {
	swapCount int // Number of bytes to swap (2 or 4)
}

// NewByteSwapMutator creates a new ByteSwapMutator
func NewByteSwapMutator(swapCount int) *ByteSwapMutator {
	if swapCount != 2 && swapCount != 4 {
		swapCount = 2
	}
	return &ByteSwapMutator{swapCount: swapCount}
}

// Name returns the mutator name
func (m *ByteSwapMutator) Name() string {
	switch m.swapCount {
	case 2:
		return "byteswap/2"
	case 4:
		return "byteswap/4"
	default:
		return "byteswap/2"
	}
}

// Description returns the mutator description
func (m *ByteSwapMutator) Description() string {
	return "Byte swap mutation for endianness testing"
}

// Type returns the mutation type
func (m *ByteSwapMutator) Type() types.MutationType {
	return types.ByteSwap
}

// Mutate applies byte swap mutation to the input
func (m *ByteSwapMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) < m.swapCount {
		return input, nil
	}

	result := make([]byte, len(input))
	copy(result, input)

	// Select random position
	pos := secureRandomInt(len(input) - m.swapCount + 1)

	// Swap bytes
	switch m.swapCount {
	case 2:
		result[pos], result[pos+1] = result[pos+1], result[pos]
	case 4:
		result[pos], result[pos+3] = result[pos+3], result[pos]
		result[pos+1], result[pos+2] = result[pos+2], result[pos+1]
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *ByteSwapMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// --- RandomByteMutator ---

// RandomByteMutator replaces bytes with random values
type RandomByteMutator struct {
	count int // Number of bytes to randomize
}

// NewRandomByteMutator creates a new RandomByteMutator
func NewRandomByteMutator(count int) *RandomByteMutator {
	if count <= 0 {
		count = 1
	}
	return &RandomByteMutator{count: count}
}

// Name returns the mutator name
func (m *RandomByteMutator) Name() string {
	return "random_byte"
}

// Description returns the mutator description
func (m *RandomByteMutator) Description() string {
	return "Replace bytes with random values"
}

// Type returns the mutation type
func (m *RandomByteMutator) Type() types.MutationType {
	return types.BitFlip
}

// Mutate applies random byte mutation to the input
func (m *RandomByteMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) == 0 {
		return input, nil
	}

	result := make([]byte, len(input))
	copy(result, input)

	count := m.count
	if count > len(input) {
		count = len(input)
	}

	// Replace random bytes with random values
	for i := 0; i < count; i++ {
		pos := secureRandomInt(len(input))
		result[pos] = byte(secureRandomInt(256))
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *RandomByteMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// --- DeleteMutator ---

// DeleteMutator deletes bytes from the input
type DeleteMutator struct {
	maxDelete int // Maximum bytes to delete
}

// NewDeleteMutator creates a new DeleteMutator
func NewDeleteMutator(maxDelete int) *DeleteMutator {
	if maxDelete <= 0 {
		maxDelete = 16
	}
	return &DeleteMutator{maxDelete: maxDelete}
}

// Name returns the mutator name
func (m *DeleteMutator) Name() string {
	return "delete"
}

// Description returns the mutator description
func (m *DeleteMutator) Description() string {
	return "Delete random bytes from input"
}

// Type returns the mutation type
func (m *DeleteMutator) Type() types.MutationType {
	return types.BitFlip
}

// Mutate deletes random bytes from the input
func (m *DeleteMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) <= 1 {
		return input, nil
	}

	// Determine how many bytes to delete
	maxDel := m.maxDelete
	if maxDel >= len(input) {
		maxDel = len(input) - 1
	}
	delCount := secureRandomInt(maxDel) + 1

	// Select random position
	pos := secureRandomInt(len(input) - delCount + 1)

	// Create result without deleted bytes
	result := make([]byte, len(input)-delCount)
	copy(result[:pos], input[:pos])
	copy(result[pos:], input[pos+delCount:])

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *DeleteMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// --- InsertMutator ---

// InsertMutator inserts bytes into the input
type InsertMutator struct {
	maxInsert int // Maximum bytes to insert
}

// NewInsertMutator creates a new InsertMutator
func NewInsertMutator(maxInsert int) *InsertMutator {
	if maxInsert <= 0 {
		maxInsert = 16
	}
	return &InsertMutator{maxInsert: maxInsert}
}

// Name returns the mutator name
func (m *InsertMutator) Name() string {
	return "insert"
}

// Description returns the mutator description
func (m *InsertMutator) Description() string {
	return "Insert random bytes into input"
}

// Type returns the mutation type
func (m *InsertMutator) Type() types.MutationType {
	return types.BitFlip
}

// Mutate inserts random bytes into the input
func (m *InsertMutator) Mutate(input []byte) ([]byte, error) {
	// Determine how many bytes to insert
	insCount := secureRandomInt(m.maxInsert) + 1

	// Select random position
	pos := secureRandomInt(len(input) + 1)

	// Generate random bytes to insert
	insertBytes := secureRandomBytes(insCount)

	// Create result with inserted bytes
	result := make([]byte, len(input)+insCount)
	copy(result[:pos], input[:pos])
	copy(result[pos:pos+insCount], insertBytes)
	if pos < len(input) {
		copy(result[pos+insCount:], input[pos:])
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *InsertMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// --- CloneMutator ---

// CloneMutator clones a portion of the input and inserts it
type CloneMutator struct {
	maxClone int // Maximum bytes to clone
}

// NewCloneMutator creates a new CloneMutator
func NewCloneMutator(maxClone int) *CloneMutator {
	if maxClone <= 0 {
		maxClone = 32
	}
	return &CloneMutator{maxClone: maxClone}
}

// Name returns the mutator name
func (m *CloneMutator) Name() string {
	return "clone"
}

// Description returns the mutator description
func (m *CloneMutator) Description() string {
	return "Clone and insert a portion of the input"
}

// Type returns the mutation type
func (m *CloneMutator) Type() types.MutationType {
	return types.BitFlip
}

// Mutate clones and inserts a portion of the input
func (m *CloneMutator) Mutate(input []byte) ([]byte, error) {
	if len(input) == 0 {
		return input, nil
	}

	// Determine how many bytes to clone
	maxCl := m.maxClone
	if maxCl > len(input) {
		maxCl = len(input)
	}
	cloneLen := secureRandomInt(maxCl) + 1

	// Select source position
	srcPos := secureRandomInt(len(input) - cloneLen + 1)

	// Select destination position
	dstPos := secureRandomInt(len(input) + 1)

	// Clone the bytes
	cloned := make([]byte, cloneLen)
	copy(cloned, input[srcPos:srcPos+cloneLen])

	// Create result with cloned bytes
	result := make([]byte, len(input)+cloneLen)
	copy(result[:dstPos], input[:dstPos])
	copy(result[dstPos:dstPos+cloneLen], cloned)
	if dstPos < len(input) {
		copy(result[dstPos+cloneLen:], input[dstPos:])
	}

	return result, nil
}

// MutateWithType applies mutation with type awareness
func (m *CloneMutator) MutateWithType(input []byte, inputType InputType) ([]byte, error) {
	return m.Mutate(input)
}

// --- Helper Functions ---

// int64ToString converts an int64 to a string without using strconv
func int64ToString(n int64) string {
	if n == 0 {
		return "0"
	}

	negative := n < 0
	if negative {
		n = -n
	}

	// Maximum digits in int64 is 19
	buf := make([]byte, 20)
	i := len(buf)

	for n > 0 {
		i--
		buf[i] = byte(n%10) + '0'
		n /= 10
	}

	if negative {
		i--
		buf[i] = '-'
	}

	return string(buf[i:])
}

// RegisterAFLMutators registers all AFL-style mutators with the given engine
func RegisterAFLMutators(engine *MutatorEngine) {
	// Bit flip mutators
	engine.Register(NewBitFlipMutator(1))
	engine.Register(NewBitFlipMutator(2))
	engine.Register(NewBitFlipMutator(4))

	// Byte flip mutators
	engine.Register(NewByteFlipMutator(1))
	engine.Register(NewByteFlipMutator(2))
	engine.Register(NewByteFlipMutator(4))

	// Arithmetic mutators
	engine.Register(NewArithmeticMutator(1, 35))
	engine.Register(NewArithmeticMutator(2, 35))
	engine.Register(NewArithmeticMutator(4, 35))

	// Interesting value mutators
	engine.Register(NewInterestingValueMutator(1))
	engine.Register(NewInterestingValueMutator(2))
	engine.Register(NewInterestingValueMutator(4))

	// Byte swap mutators
	engine.Register(NewByteSwapMutator(2))
	engine.Register(NewByteSwapMutator(4))

	// Other mutators
	engine.Register(NewRandomByteMutator(1))
	engine.Register(NewDeleteMutator(16))
	engine.Register(NewInsertMutator(16))
	engine.Register(NewCloneMutator(32))
}

// GetInteresting8 returns the list of interesting 8-bit values
func GetInteresting8() []int8 {
	return interesting8
}

// GetInteresting16 returns the list of interesting 16-bit values
func GetInteresting16() []int16 {
	return interesting16
}

// GetInteresting32 returns the list of interesting 32-bit values
func GetInteresting32() []int32 {
	return interesting32
}
