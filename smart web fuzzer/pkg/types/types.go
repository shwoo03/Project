// Package types defines common data structures used across FluxFuzzer components.
package types

import (
	"time"
)

// MutationType defines the type of mutation to apply
type MutationType int

const (
	BitFlip           MutationType = iota // AFL-style bit flipping
	ByteSwap                              // Byte position swapping
	ArithmeticAdd                         // Arithmetic operations (overflow)
	InterestingValues                     // Boundary values (0, -1, MAX_INT)
	DictionaryInsert                      // Wordlist-based insertion
	StructureAware                        // JSON/XML structure-aware mutation
)

// Severity indicates the severity level of an anomaly
type Severity int

const (
	Info Severity = iota
	Low
	Medium
	High
	Critical
)

// FuzzTarget represents a fuzzing target with its configuration
type FuzzTarget struct {
	Method      string            // HTTP method (GET, POST, etc.)
	URL         string            // Target URL
	PayloadTmpl string            // Payload template: "id={{user_id}}&name={{random_str}}"
	Headers     map[string]string // HTTP headers
	Body        []byte            // Request body
	StateKeys   []string          // Variables to extract from response
}

// Response wraps an HTTP response with metadata
type Response struct {
	RequestID    string              // Unique request identifier
	StatusCode   int                 // HTTP status code
	Headers      map[string][]string // Response headers
	Body         []byte              // Response body
	ResponseTime time.Duration       // Time taken for the request
	Error        error               // Any error that occurred
}

// AnomalyResult represents the analysis result for anomaly detection
type AnomalyResult struct {
	RequestID  string   // Reference to the request
	Distance   int      // Structural distance (0~64)
	TimeSkew   float64  // Response time ratio (e.g., 2.5x slower)
	LengthDiff int      // Body length difference
	IsCrash    bool     // Whether a 500 error occurred
	Evidence   string   // Reason for detection
	Severity   Severity // Severity level
}

// Baseline stores the baseline metrics for comparison
type Baseline struct {
	AvgResponseTime time.Duration // Average response time
	StdDevTime      time.Duration // Standard deviation of response time
	AvgBodyLength   int           // Average body length
	StdDevLength    int           // Standard deviation of body length
	StructureHash   uint64        // SimHash of normal response structure
	SampleCount     int           // Number of samples collected
}

// MutationResult represents a mutated payload
type MutationResult struct {
	Original []byte       // Original payload
	Mutated  []byte       // Mutated payload
	Type     MutationType // Type of mutation applied
}
