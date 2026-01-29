// Package state provides template substitution for dynamic value replacement.
// It supports {{variable}} syntax, built-in functions, and conditional substitution.
package state

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

// TemplateEngine handles template parsing and substitution
type TemplateEngine struct {
	mu        sync.RWMutex
	pool      *Pool
	functions map[string]TemplateFunc
	variables map[string]string
}

// TemplateFunc is a function that generates dynamic values
type TemplateFunc func(args ...string) string

// NewTemplateEngine creates a new TemplateEngine with optional pool
func NewTemplateEngine(pool *Pool) *TemplateEngine {
	e := &TemplateEngine{
		pool:      pool,
		functions: make(map[string]TemplateFunc),
		variables: make(map[string]string),
	}

	// Register built-in functions
	e.registerBuiltInFunctions()

	return e
}

// registerBuiltInFunctions adds all built-in template functions
func (e *TemplateEngine) registerBuiltInFunctions() {
	// Random string generators
	e.RegisterFunction("random_str", func(args ...string) string {
		length := 8
		if len(args) > 0 {
			if n, err := strconv.Atoi(args[0]); err == nil && n > 0 {
				length = n
			}
		}
		return randomString(length)
	})

	e.RegisterFunction("random_hex", func(args ...string) string {
		length := 16
		if len(args) > 0 {
			if n, err := strconv.Atoi(args[0]); err == nil && n > 0 {
				length = n
			}
		}
		return randomHex(length)
	})

	e.RegisterFunction("random_int", func(args ...string) string {
		min, max := 0, 1000000
		if len(args) >= 2 {
			if n, err := strconv.Atoi(args[0]); err == nil {
				min = n
			}
			if n, err := strconv.Atoi(args[1]); err == nil {
				max = n
			}
		}
		return strconv.Itoa(randomInt(min, max))
	})

	// Time functions
	e.RegisterFunction("timestamp", func(args ...string) string {
		return strconv.FormatInt(time.Now().Unix(), 10)
	})

	e.RegisterFunction("timestamp_ms", func(args ...string) string {
		return strconv.FormatInt(time.Now().UnixMilli(), 10)
	})

	e.RegisterFunction("datetime", func(args ...string) string {
		format := "2006-01-02T15:04:05Z"
		if len(args) > 0 {
			format = args[0]
		}
		return time.Now().Format(format)
	})

	e.RegisterFunction("date", func(args ...string) string {
		return time.Now().Format("2006-01-02")
	})

	// UUID-like generator
	e.RegisterFunction("uuid", func(args ...string) string {
		return generateUUID()
	})

	// Environment variable
	e.RegisterFunction("env", func(args ...string) string {
		if len(args) > 0 {
			if val := os.Getenv(args[0]); val != "" {
				return val
			}
			if len(args) > 1 {
				return args[1] // default value
			}
		}
		return ""
	})

	// String manipulation
	e.RegisterFunction("upper", func(args ...string) string {
		if len(args) > 0 {
			return strings.ToUpper(args[0])
		}
		return ""
	})

	e.RegisterFunction("lower", func(args ...string) string {
		if len(args) > 0 {
			return strings.ToLower(args[0])
		}
		return ""
	})

	e.RegisterFunction("base64", func(args ...string) string {
		if len(args) > 0 {
			return base64Encode(args[0])
		}
		return ""
	})

	e.RegisterFunction("urlencode", func(args ...string) string {
		if len(args) > 0 {
			return urlEncode(args[0])
		}
		return ""
	})

	// Counter (increments each call)
	counter := 0
	e.RegisterFunction("counter", func(args ...string) string {
		counter++
		return strconv.Itoa(counter)
	})

	// Sequence
	e.RegisterFunction("seq", func(args ...string) string {
		if len(args) > 0 {
			return args[randomInt(0, len(args))]
		}
		return ""
	})
}

// RegisterFunction adds a custom template function
func (e *TemplateEngine) RegisterFunction(name string, fn TemplateFunc) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.functions[name] = fn
}

// SetVariable sets a static variable value
func (e *TemplateEngine) SetVariable(name, value string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.variables[name] = value
}

// SetVariables sets multiple static variable values
func (e *TemplateEngine) SetVariables(vars map[string]string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	for name, value := range vars {
		e.variables[name] = value
	}
}

// Template patterns
var (
	// {{name}} or {{name:default}}
	simpleVarPattern = regexp.MustCompile(`\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]*))?\}\}`)

	// {{func()}} or {{func(arg1, arg2)}}
	functionPattern = regexp.MustCompile(`\{\{([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)\}\}`)

	// {{?condition:value_if_true:value_if_false}}
	conditionalPattern = regexp.MustCompile(`\{\{\?([^:]+):([^:]*):([^}]*)\}\}`)
)

// Substitute replaces all template variables in the input
func (e *TemplateEngine) Substitute(input string) string {
	e.mu.RLock()
	defer e.mu.RUnlock()

	result := input

	// Process functions first: {{func(args)}}
	result = functionPattern.ReplaceAllStringFunc(result, func(match string) string {
		groups := functionPattern.FindStringSubmatch(match)
		if len(groups) < 3 {
			return match
		}

		funcName := groups[1]
		argsStr := strings.TrimSpace(groups[2])

		var args []string
		if argsStr != "" {
			for _, arg := range strings.Split(argsStr, ",") {
				args = append(args, strings.TrimSpace(arg))
			}
		}

		if fn, exists := e.functions[funcName]; exists {
			return fn(args...)
		}

		return match
	})

	// Process conditionals: {{?condition:true:false}}
	result = conditionalPattern.ReplaceAllStringFunc(result, func(match string) string {
		groups := conditionalPattern.FindStringSubmatch(match)
		if len(groups) < 4 {
			return match
		}

		condition := strings.TrimSpace(groups[1])
		trueValue := groups[2]
		falseValue := groups[3]

		// Evaluate condition
		if e.evaluateCondition(condition) {
			return trueValue
		}
		return falseValue
	})

	// Process simple variables: {{name}} or {{name:default}}
	result = simpleVarPattern.ReplaceAllStringFunc(result, func(match string) string {
		groups := simpleVarPattern.FindStringSubmatch(match)
		if len(groups) < 2 {
			return match
		}

		varName := groups[1]
		defaultValue := ""
		if len(groups) > 2 {
			defaultValue = groups[2]
		}

		// Check static variables first
		if val, exists := e.variables[varName]; exists {
			return val
		}

		// Check pool
		if e.pool != nil {
			if val, found := e.pool.GetLatest(varName); found {
				return val
			}
		}

		// Check environment
		if val := os.Getenv(varName); val != "" {
			return val
		}

		// Return default or original
		if defaultValue != "" {
			return defaultValue
		}

		return match
	})

	return result
}

// SubstituteBytes is a convenience method for byte slices
func (e *TemplateEngine) SubstituteBytes(input []byte) []byte {
	return []byte(e.Substitute(string(input)))
}

// evaluateCondition evaluates a simple condition
func (e *TemplateEngine) evaluateCondition(condition string) bool {
	condition = strings.TrimSpace(condition)

	// Check if variable exists
	if strings.HasPrefix(condition, "exists:") {
		varName := strings.TrimPrefix(condition, "exists:")
		return e.hasValue(strings.TrimSpace(varName))
	}

	// Check equality: var==value
	if strings.Contains(condition, "==") {
		parts := strings.SplitN(condition, "==", 2)
		if len(parts) == 2 {
			leftVal := e.getValue(strings.TrimSpace(parts[0]))
			rightVal := strings.TrimSpace(parts[1])
			return leftVal == rightVal
		}
	}

	// Check inequality: var!=value
	if strings.Contains(condition, "!=") {
		parts := strings.SplitN(condition, "!=", 2)
		if len(parts) == 2 {
			leftVal := e.getValue(strings.TrimSpace(parts[0]))
			rightVal := strings.TrimSpace(parts[1])
			return leftVal != rightVal
		}
	}

	// Simple truthy check - variable has non-empty value
	return e.hasValue(condition)
}

// hasValue checks if a variable has a value
func (e *TemplateEngine) hasValue(name string) bool {
	if _, exists := e.variables[name]; exists {
		return true
	}
	if e.pool != nil && e.pool.Has(name) {
		return true
	}
	return os.Getenv(name) != ""
}

// getValue gets a variable value
func (e *TemplateEngine) getValue(name string) string {
	if val, exists := e.variables[name]; exists {
		return val
	}
	if e.pool != nil {
		if val, found := e.pool.GetLatest(name); found {
			return val
		}
	}
	return os.Getenv(name)
}

// HasUnresolved checks if the template has unresolved variables
func (e *TemplateEngine) HasUnresolved(input string) bool {
	return simpleVarPattern.MatchString(input) || functionPattern.MatchString(input)
}

// ExtractVariables returns all variable names in the template
func (e *TemplateEngine) ExtractVariables(input string) []string {
	var vars []string
	seen := make(map[string]bool)

	matches := simpleVarPattern.FindAllStringSubmatch(input, -1)
	for _, m := range matches {
		if len(m) > 1 && !seen[m[1]] {
			vars = append(vars, m[1])
			seen[m[1]] = true
		}
	}

	return vars
}

// --- Helper Functions ---

func randomString(length int) string {
	const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	result := make([]byte, length)
	randBytes := make([]byte, length)
	rand.Read(randBytes)
	for i := 0; i < length; i++ {
		result[i] = chars[int(randBytes[i])%len(chars)]
	}
	return string(result)
}

func randomHex(length int) string {
	bytes := make([]byte, (length+1)/2)
	rand.Read(bytes)
	return hex.EncodeToString(bytes)[:length]
}

func randomInt(min, max int) int {
	if min >= max {
		return min
	}
	randBytes := make([]byte, 4)
	rand.Read(randBytes)
	n := int(randBytes[0])<<24 | int(randBytes[1])<<16 | int(randBytes[2])<<8 | int(randBytes[3])
	if n < 0 {
		n = -n
	}
	return min + (n % (max - min))
}

func generateUUID() string {
	bytes := make([]byte, 16)
	rand.Read(bytes)
	bytes[6] = (bytes[6] & 0x0f) | 0x40 // Version 4
	bytes[8] = (bytes[8] & 0x3f) | 0x80 // Variant
	return fmt.Sprintf("%x-%x-%x-%x-%x",
		bytes[0:4], bytes[4:6], bytes[6:8], bytes[8:10], bytes[10:16])
}

func base64Encode(s string) string {
	const base64Chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	input := []byte(s)
	result := make([]byte, 0, (len(input)+2)/3*4)

	for i := 0; i < len(input); i += 3 {
		var n uint32
		n = uint32(input[i]) << 16
		if i+1 < len(input) {
			n |= uint32(input[i+1]) << 8
		}
		if i+2 < len(input) {
			n |= uint32(input[i+2])
		}

		result = append(result, base64Chars[(n>>18)&0x3f])
		result = append(result, base64Chars[(n>>12)&0x3f])
		if i+1 < len(input) {
			result = append(result, base64Chars[(n>>6)&0x3f])
		} else {
			result = append(result, '=')
		}
		if i+2 < len(input) {
			result = append(result, base64Chars[n&0x3f])
		} else {
			result = append(result, '=')
		}
	}

	return string(result)
}

func urlEncode(s string) string {
	var result strings.Builder
	result.Grow(len(s) * 3)

	for i := 0; i < len(s); i++ {
		c := s[i]
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
			c == '-' || c == '_' || c == '.' || c == '~' {
			result.WriteByte(c)
		} else {
			result.WriteByte('%')
			result.WriteByte("0123456789ABCDEF"[c>>4])
			result.WriteByte("0123456789ABCDEF"[c&0xf])
		}
	}

	return result.String()
}

// --- State Manager ---

// StateManager coordinates extraction, pool, and template substitution
type StateManager struct {
	pool      *Pool
	extractor *Extractor
	engine    *TemplateEngine
}

// NewStateManager creates a new StateManager
func NewStateManager() *StateManager {
	pool := NewPool(nil)
	return &StateManager{
		pool:      pool,
		extractor: NewExtractor(),
		engine:    NewTemplateEngine(pool),
	}
}

// NewStateManagerWithConfig creates a StateManager with custom pool config
func NewStateManagerWithConfig(poolConfig *PoolConfig) *StateManager {
	pool := NewPool(poolConfig)
	return &StateManager{
		pool:      pool,
		extractor: NewExtractor(),
		engine:    NewTemplateEngine(pool),
	}
}

// Pool returns the underlying pool
func (m *StateManager) Pool() *Pool {
	return m.pool
}

// Extractor returns the underlying extractor
func (m *StateManager) Extractor() *Extractor {
	return m.extractor
}

// Engine returns the underlying template engine
func (m *StateManager) Engine() *TemplateEngine {
	return m.engine
}

// ExtractAndStore extracts values from input and stores them in the pool
func (m *StateManager) ExtractAndStore(input *ExtractionInput) []ExtractionResult {
	results := m.extractor.Extract(input)

	for _, result := range results {
		if result.Found && result.Value != "" {
			m.pool.AddWithSource(result.Name, result.Value, result.Source)
		}
	}

	return results
}

// Substitute replaces template variables using pool values
func (m *StateManager) Substitute(input string) string {
	return m.engine.Substitute(input)
}

// SubstituteBytes replaces template variables in byte slice
func (m *StateManager) SubstituteBytes(input []byte) []byte {
	return m.engine.SubstituteBytes(input)
}

// SetVariable sets a static variable
func (m *StateManager) SetVariable(name, value string) {
	m.engine.SetVariable(name, value)
}

// AddExtractionRule adds an extraction rule
func (m *StateManager) AddExtractionRule(rule *ExtractionRule) error {
	return m.extractor.AddRule(rule)
}

// Close releases resources
func (m *StateManager) Close() {
	m.pool.Close()
}
