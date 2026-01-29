// Package mutator provides mutation strategies for payload transformation.
// It implements various mutation techniques including AFL-style bit flipping,
// type-aware smart mutations, and random selection strategies.
package mutator

import (
	"crypto/rand"
	"encoding/binary"
	"sync"

	"github.com/fluxfuzzer/fluxfuzzer/pkg/types"
)

// Mutator defines the interface for all mutation implementations
type Mutator interface {
	// Name returns the human-readable name of the mutator
	Name() string

	// Description returns a brief description of what this mutator does
	Description() string

	// Mutate applies the mutation strategy to the input
	Mutate(input []byte) ([]byte, error)

	// MutateWithType applies mutation based on inferred type
	MutateWithType(input []byte, inputType InputType) ([]byte, error)

	// Type returns the MutationType constant for this mutator
	Type() types.MutationType
}

// MutationStrategy defines how mutations are selected and applied
type MutationStrategy interface {
	// SelectMutator chooses a mutator from the available pool
	SelectMutator(mutators []Mutator) Mutator

	// ShouldMutate decides whether to apply mutation
	ShouldMutate(probability float64) bool

	// Reset resets any internal state
	Reset()
}

// InputType represents the detected type of input data
type InputType int

const (
	TypeUnknown InputType = iota
	TypeString
	TypeInteger
	TypeFloat
	TypeJSON
	TypeXML
	TypeHTML
	TypeURL
	TypeEmail
	TypeUUID
	TypeJWT
	TypeBase64
	TypeHex
)

// String returns the string representation of InputType
func (t InputType) String() string {
	switch t {
	case TypeString:
		return "string"
	case TypeInteger:
		return "integer"
	case TypeFloat:
		return "float"
	case TypeJSON:
		return "json"
	case TypeXML:
		return "xml"
	case TypeHTML:
		return "html"
	case TypeURL:
		return "url"
	case TypeEmail:
		return "email"
	case TypeUUID:
		return "uuid"
	case TypeJWT:
		return "jwt"
	case TypeBase64:
		return "base64"
	case TypeHex:
		return "hex"
	default:
		return "unknown"
	}
}

// MutationResult wraps the result of a mutation operation
type MutationResult struct {
	Original    []byte
	Mutated     []byte
	MutatorName string
	InputType   InputType
	Success     bool
	Error       error
}

// --- Registry: Manages available mutators ---

// Registry stores and manages available mutators
type Registry struct {
	mu       sync.RWMutex
	mutators map[string]Mutator
	order    []string // maintains insertion order
}

// NewRegistry creates a new mutator registry
func NewRegistry() *Registry {
	return &Registry{
		mutators: make(map[string]Mutator),
		order:    make([]string, 0),
	}
}

// Register adds a mutator to the registry
func (r *Registry) Register(m Mutator) {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := m.Name()
	if _, exists := r.mutators[name]; !exists {
		r.order = append(r.order, name)
	}
	r.mutators[name] = m
}

// Get retrieves a mutator by name
func (r *Registry) Get(name string) (Mutator, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	m, exists := r.mutators[name]
	return m, exists
}

// GetByType retrieves mutators by MutationType
func (r *Registry) GetByType(t types.MutationType) []Mutator {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var result []Mutator
	for _, name := range r.order {
		if m, exists := r.mutators[name]; exists && m.Type() == t {
			result = append(result, m)
		}
	}
	return result
}

// All returns all registered mutators in insertion order
func (r *Registry) All() []Mutator {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]Mutator, 0, len(r.order))
	for _, name := range r.order {
		if m, exists := r.mutators[name]; exists {
			result = append(result, m)
		}
	}
	return result
}

// Names returns the names of all registered mutators
func (r *Registry) Names() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]string, len(r.order))
	copy(result, r.order)
	return result
}

// Count returns the number of registered mutators
func (r *Registry) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.mutators)
}

// Remove removes a mutator from the registry
func (r *Registry) Remove(name string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.mutators[name]; !exists {
		return false
	}

	delete(r.mutators, name)

	// Remove from order slice
	for i, n := range r.order {
		if n == name {
			r.order = append(r.order[:i], r.order[i+1:]...)
			break
		}
	}

	return true
}

// --- RandomSelector: Random mutation selection strategy ---

// RandomSelector implements random mutator selection
type RandomSelector struct {
	mu sync.Mutex
}

// NewRandomSelector creates a new RandomSelector
func NewRandomSelector() *RandomSelector {
	return &RandomSelector{}
}

// SelectMutator randomly selects a mutator from the pool
func (s *RandomSelector) SelectMutator(mutators []Mutator) Mutator {
	if len(mutators) == 0 {
		return nil
	}

	idx := secureRandomInt(len(mutators))
	return mutators[idx]
}

// ShouldMutate decides whether to apply mutation based on probability
func (s *RandomSelector) ShouldMutate(probability float64) bool {
	if probability <= 0 {
		return false
	}
	if probability >= 1.0 {
		return true
	}

	// Generate random float between 0 and 1
	randFloat := float64(secureRandomInt(10000)) / 10000.0
	return randFloat < probability
}

// Reset resets any internal state (no-op for RandomSelector)
func (s *RandomSelector) Reset() {
	// No internal state to reset
}

// --- WeightedSelector: Weighted random selection ---

// WeightedSelector implements weighted mutator selection
type WeightedSelector struct {
	mu      sync.Mutex
	weights map[string]float64
}

// NewWeightedSelector creates a new WeightedSelector
func NewWeightedSelector() *WeightedSelector {
	return &WeightedSelector{
		weights: make(map[string]float64),
	}
}

// SetWeight sets the selection weight for a mutator
func (s *WeightedSelector) SetWeight(name string, weight float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if weight > 0 {
		s.weights[name] = weight
	}
}

// SelectMutator selects a mutator based on weights
func (s *WeightedSelector) SelectMutator(mutators []Mutator) Mutator {
	s.mu.Lock()
	defer s.mu.Unlock()

	if len(mutators) == 0 {
		return nil
	}

	// Calculate total weight
	var totalWeight float64
	for _, m := range mutators {
		if w, exists := s.weights[m.Name()]; exists {
			totalWeight += w
		} else {
			totalWeight += 1.0 // default weight
		}
	}

	if totalWeight <= 0 {
		return mutators[secureRandomInt(len(mutators))]
	}

	// Select based on weight
	target := float64(secureRandomInt(10000)) / 10000.0 * totalWeight
	var cumulative float64

	for _, m := range mutators {
		weight := 1.0
		if w, exists := s.weights[m.Name()]; exists {
			weight = w
		}
		cumulative += weight
		if cumulative >= target {
			return m
		}
	}

	return mutators[len(mutators)-1]
}

// ShouldMutate decides whether to apply mutation based on probability
func (s *WeightedSelector) ShouldMutate(probability float64) bool {
	if probability <= 0 {
		return false
	}
	if probability >= 1.0 {
		return true
	}
	randFloat := float64(secureRandomInt(10000)) / 10000.0
	return randFloat < probability
}

// Reset resets internal state
func (s *WeightedSelector) Reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.weights = make(map[string]float64)
}

// --- MutatorEngine: Main mutation orchestrator ---

// MutatorEngine orchestrates mutation operations
type MutatorEngine struct {
	mu              sync.RWMutex
	registry        *Registry
	strategy        MutationStrategy
	probability     float64
	maxMutations    int
	typeDetectors   []TypeDetector
	defaultMutators []string
}

// TypeDetector detects the type of input
type TypeDetector func(input []byte) (InputType, bool)

// MutatorEngineConfig holds configuration for MutatorEngine
type MutatorEngineConfig struct {
	Probability     float64          // Probability of mutation (0.0 - 1.0)
	MaxMutations    int              // Maximum mutations to apply in chain
	Strategy        MutationStrategy // Selection strategy
	DefaultMutators []string         // Names of default mutators to use
}

// DefaultEngineConfig returns default configuration
func DefaultEngineConfig() *MutatorEngineConfig {
	return &MutatorEngineConfig{
		Probability:     1.0,
		MaxMutations:    1,
		Strategy:        NewRandomSelector(),
		DefaultMutators: nil, // use all registered
	}
}

// NewMutatorEngine creates a new MutatorEngine with default configuration
func NewMutatorEngine() *MutatorEngine {
	return NewMutatorEngineWithConfig(DefaultEngineConfig())
}

// NewMutatorEngineWithConfig creates a new MutatorEngine with custom configuration
func NewMutatorEngineWithConfig(config *MutatorEngineConfig) *MutatorEngine {
	if config == nil {
		config = DefaultEngineConfig()
	}

	engine := &MutatorEngine{
		registry:        NewRegistry(),
		strategy:        config.Strategy,
		probability:     config.Probability,
		maxMutations:    config.MaxMutations,
		typeDetectors:   make([]TypeDetector, 0),
		defaultMutators: config.DefaultMutators,
	}

	// Register built-in type detectors
	engine.registerBuiltInDetectors()

	return engine
}

// registerBuiltInDetectors adds default type detection functions
func (e *MutatorEngine) registerBuiltInDetectors() {
	// JSON detector
	e.AddTypeDetector(func(input []byte) (InputType, bool) {
		if len(input) < 2 {
			return TypeUnknown, false
		}
		// Simple check for JSON object or array
		first := input[0]
		if first == '{' || first == '[' {
			return TypeJSON, true
		}
		return TypeUnknown, false
	})

	// XML detector
	e.AddTypeDetector(func(input []byte) (InputType, bool) {
		if len(input) < 1 {
			return TypeUnknown, false
		}
		if input[0] == '<' {
			return TypeXML, true
		}
		return TypeUnknown, false
	})

	// Integer detector
	e.AddTypeDetector(func(input []byte) (InputType, bool) {
		if len(input) == 0 {
			return TypeUnknown, false
		}
		for i, b := range input {
			if b == '-' && i == 0 {
				continue
			}
			if b < '0' || b > '9' {
				return TypeUnknown, false
			}
		}
		return TypeInteger, true
	})

	// UUID detector
	e.AddTypeDetector(func(input []byte) (InputType, bool) {
		if len(input) != 36 {
			return TypeUnknown, false
		}
		// Check format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
		s := string(input)
		if s[8] != '-' || s[13] != '-' || s[18] != '-' || s[23] != '-' {
			return TypeUnknown, false
		}
		return TypeUUID, true
	})
}

// Register adds a mutator to the engine
func (e *MutatorEngine) Register(m Mutator) {
	e.registry.Register(m)
}

// AddTypeDetector adds a custom type detector
func (e *MutatorEngine) AddTypeDetector(detector TypeDetector) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.typeDetectors = append(e.typeDetectors, detector)
}

// SetStrategy sets the mutation selection strategy
func (e *MutatorEngine) SetStrategy(strategy MutationStrategy) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.strategy = strategy
}

// SetProbability sets the mutation probability
func (e *MutatorEngine) SetProbability(p float64) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if p < 0 {
		p = 0
	}
	if p > 1 {
		p = 1
	}
	e.probability = p
}

// DetectType attempts to detect the input type
func (e *MutatorEngine) DetectType(input []byte) InputType {
	e.mu.RLock()
	defer e.mu.RUnlock()

	for _, detector := range e.typeDetectors {
		if t, detected := detector(input); detected {
			return t
		}
	}
	return TypeUnknown
}

// Mutate applies a single random mutation to the input
func (e *MutatorEngine) Mutate(input []byte) *MutationResult {
	e.mu.RLock()
	probability := e.probability
	strategy := e.strategy
	e.mu.RUnlock()

	result := &MutationResult{
		Original:  input,
		Mutated:   input,
		InputType: e.DetectType(input),
	}

	// Check if we should mutate
	if !strategy.ShouldMutate(probability) {
		result.Success = true
		return result
	}

	// Get available mutators
	mutators := e.getActiveMutators()
	if len(mutators) == 0 {
		result.Success = true
		return result
	}

	// Select and apply mutator
	mutator := strategy.SelectMutator(mutators)
	if mutator == nil {
		result.Success = true
		return result
	}

	mutated, err := mutator.MutateWithType(input, result.InputType)
	if err != nil {
		result.Error = err
		result.Success = false
		return result
	}

	result.Mutated = mutated
	result.MutatorName = mutator.Name()
	result.Success = true

	return result
}

// MutateN applies N random mutations to the input
func (e *MutatorEngine) MutateN(input []byte, n int) *MutationResult {
	if n <= 0 {
		return &MutationResult{
			Original: input,
			Mutated:  input,
			Success:  true,
		}
	}

	current := input
	var lastMutator string
	inputType := e.DetectType(input)

	for i := 0; i < n; i++ {
		result := e.Mutate(current)
		if result.Error != nil {
			return result
		}
		current = result.Mutated
		if result.MutatorName != "" {
			lastMutator = result.MutatorName
		}
	}

	return &MutationResult{
		Original:    input,
		Mutated:     current,
		MutatorName: lastMutator,
		InputType:   inputType,
		Success:     true,
	}
}

// MutateChain applies a chain of mutations up to maxMutations
func (e *MutatorEngine) MutateChain(input []byte) *MutationResult {
	e.mu.RLock()
	maxMutations := e.maxMutations
	e.mu.RUnlock()

	if maxMutations <= 0 {
		maxMutations = 1
	}

	// Random number of mutations between 1 and maxMutations
	n := secureRandomInt(maxMutations) + 1
	return e.MutateN(input, n)
}

// getActiveMutators returns mutators to use based on configuration
func (e *MutatorEngine) getActiveMutators() []Mutator {
	if len(e.defaultMutators) == 0 {
		return e.registry.All()
	}

	var mutators []Mutator
	for _, name := range e.defaultMutators {
		if m, exists := e.registry.Get(name); exists {
			mutators = append(mutators, m)
		}
	}
	return mutators
}

// Registry returns the underlying registry
func (e *MutatorEngine) Registry() *Registry {
	return e.registry
}

// --- Helper functions ---

// secureRandomInt generates a cryptographically secure random number in [0, max)
func secureRandomInt(max int) int {
	if max <= 0 {
		return 0
	}

	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return 0
	}

	n := binary.BigEndian.Uint64(b[:])
	return int(n % uint64(max))
}

// secureRandomBytes generates cryptographically secure random bytes
func secureRandomBytes(n int) []byte {
	b := make([]byte, n)
	rand.Read(b)
	return b
}
